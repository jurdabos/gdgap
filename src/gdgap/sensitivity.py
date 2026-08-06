"""
Imputation sensitivity audit: R3's provenance payoff as a reproducible report.

Westat completed missing sex values by random hot-deck imputation within adjustment
cells (2017 NHTS Weighting Report, Appendix D); the public files expose original and
completed values but not donor assignments, so individual imputations cannot be
reconstructed or validated. This audit therefore quantifies influence, not bias —
an imputation sensitivity audit, not a bias detector.

Frozen scenario definitions:
- all_completed: every current person, grouped by the completed code (baseline,
  reproducing the v_care_trip_share_by_sex / v_ppr semantics);
- observed_only: rows with sex_source = 'imputed' excluded; edited rows keep the
  completed code;
- reported_values: imputed rows excluded; edited rows grouped by sex_code_reported.

Published weights were raked with the completed sex, so scenario estimates are
sensitivity scenarios under the published weights, never re-raked estimators. Equity
cells below n >= 30 stay suppressed (R9, exposure); small rate numerators are flagged
unstable instead (statistical instability, not exposure). Outputs regenerate
deterministically (snapshot and commit columns, fixed float formats, no timestamps in
CSVs) under results/sensitivity/<dataset>/; only the markdown carries a generation time.
"""

import csv
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import click
from tabulate import tabulate

from gdgap.bench.run import _git_commit
from gdgap.ingest.nhts2017 import DATASET, _chdir, _connect, find_root

SENSITIVITY_DIR = Path("results/sensitivity") / DATASET
SUMMARY_FILE = "sensitivity_summary.md"
CARE_CODE = "06"
SUPPRESS_N = 30
DIM = "lake.aware.dim_person_sex"
FACT_PERSON = "lake.aware.fact_person"
FACT_TRIP = "lake.aware.fact_trip"
# Scenario name, dimension-row inclusion predicate, and group-code expression (frozen definitions)
SCENARIOS = (
    ("all_completed", "true", "d.sex_code"),
    ("observed_only", "d.sex_source <> 'imputed'", "d.sex_code"),
    (
        "reported_values",
        "d.sex_source <> 'imputed'",
        "case when d.sex_source = 'edited' then d.sex_code_reported else d.sex_code end",
    ),
)
AGE_BAND_SQL = (
    "case when f.r_age < 0 then 'reserve' when f.r_age < 18 then '0-17' "
    "when f.r_age < 40 then '18-39' when f.r_age < 65 then '40-64' else '65plus' end"
)
SPLIT_FIELDS = [
    "snapshot",
    "git_commit",
    "sex_source",
    "persons_n",
    "persons_pct",
    "person_weight",
    "person_weight_pct",
    "trips_n",
    "trips_pct",
    "trip_weight",
    "trip_weight_pct",
]
RATE_FIELDS = [
    "snapshot",
    "git_commit",
    "dimension",
    "category",
    "persons_n",
    "imputed_n",
    "imputed_rate_pct",
    "imputed_unstable",
    "edited_n",
    "edited_rate_pct",
    "edited_unstable",
    "non_reported_n",
    "non_reported_rate_pct",
]
EQUITY_FIELDS = [
    "snapshot",
    "git_commit",
    "measure",
    "scenario",
    "sex_code",
    "persons_n",
    "person_weight",
    "trips_n",
    "trip_weight",
    "care_weight",
    "value",
    "suppressed",
    "delta_vs_all_completed",
]
COVERAGE_FIELDS = [
    "snapshot",
    "git_commit",
    "scenario",
    "persons_excluded_n",
    "person_weight_excluded_pct",
    "trips_excluded_n",
    "trip_weight_excluded_pct",
    "persons_reclassified_n",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    """Writes a CSV afresh — deterministic regeneration, never an append."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _pct(part: float, total: float) -> str:
    """Returns a fixed-format percentage share, empty when the total is zero."""
    return f"{100.0 * part / total:.4f}" if total else ""


def _provenance_split(con, base: dict) -> list[dict]:
    """Returns per-sex_source person and trip counts with weight shares."""
    rows = con.execute(
        f"""
        with person as (
            select d.sex_source, count(*) as persons_n, sum(f.wtperfin) as person_weight
            from {DIM} d
            join {FACT_PERSON} f on f.houseid = d.houseid and f.personid = d.personid
            where d.is_current
            group by 1
        ),
        trip as (
            select d.sex_source, count(*) as trips_n, sum(t.wttrdfin) as trip_weight
            from {DIM} d
            join {FACT_TRIP} t on t.houseid = d.houseid and t.personid = d.personid
            where d.is_current
            group by 1
        )
        select person.sex_source, persons_n, person_weight,
               coalesce(trips_n, 0), coalesce(trip_weight, 0.0)
        from person left join trip on trip.sex_source = person.sex_source
        order by 1
        """
    ).fetchall()
    persons_total = sum(row[1] for row in rows)
    person_weight_total = sum(row[2] for row in rows)
    trips_total = sum(row[3] for row in rows)
    trip_weight_total = sum(row[4] for row in rows)
    return [
        base
        | {
            "sex_source": source,
            "persons_n": persons_n,
            "persons_pct": _pct(persons_n, persons_total),
            "person_weight": f"{person_weight:.1f}",
            "person_weight_pct": _pct(person_weight, person_weight_total),
            "trips_n": trips_n,
            "trips_pct": _pct(trips_n, trips_total),
            "trip_weight": f"{trip_weight:.1f}",
            "trip_weight_pct": _pct(trip_weight, trip_weight_total),
        }
        for source, persons_n, person_weight, trips_n, trip_weight in rows
    ]


def _rate_row(base: dict, dimension: str, category: str, total: int, imputed: int, edited: int) -> dict:
    """Returns one imputation_rates row with instability flags (numerator < 30)."""
    return base | {
        "dimension": dimension,
        "category": category,
        "persons_n": total,
        "imputed_n": imputed,
        "imputed_rate_pct": _pct(imputed, total),
        "imputed_unstable": imputed < SUPPRESS_N,
        "edited_n": edited,
        "edited_rate_pct": _pct(edited, total),
        "edited_unstable": edited < SUPPRESS_N,
        "non_reported_n": imputed + edited,
        "non_reported_rate_pct": _pct(imputed + edited, total),
    }


def _imputation_rates(con, base: dict) -> list[dict]:
    """Returns one-dimensional non-reported rates by completed code and by age band."""
    queries = {
        "completed_sex_code": (
            f"select d.sex_code as category, count(*),"
            f" count(*) filter (where d.sex_source = 'imputed'),"
            f" count(*) filter (where d.sex_source = 'edited')"
            f" from {DIM} d where d.is_current group by 1 order by 1"
        ),
        "age_band": (
            f"select {AGE_BAND_SQL} as category, count(*),"
            f" count(*) filter (where d.sex_source = 'imputed'),"
            f" count(*) filter (where d.sex_source = 'edited')"
            f" from {DIM} d join {FACT_PERSON} f on f.houseid = d.houseid and f.personid = d.personid"
            f" where d.is_current group by 1 order by 1"
        ),
    }
    out: list[dict] = []
    for dimension, sql in queries.items():
        rows = con.execute(sql).fetchall()
        for category, total, imputed, edited in rows:
            out.append(_rate_row(base, dimension, str(category), total, imputed, edited))
        out.append(
            _rate_row(
                base,
                dimension,
                "TOTAL",
                sum(row[1] for row in rows),
                sum(row[2] for row in rows),
                sum(row[3] for row in rows),
            )
        )
    return out


def _care_share_rows(con, base: dict) -> list[dict]:
    """Returns care_trip_share rows per scenario and group, R9-suppressed below n >= 30."""
    out: list[dict] = []
    baseline: dict[str, float] = {}
    for scenario, include, group in SCENARIOS:
        rows = con.execute(
            f"""
            select {group} as sex_code, count(*) as trips_n, sum(t.wttrdfin) as trip_weight,
                   sum(case when t.whyto = '{CARE_CODE}' or t.whyfrom = '{CARE_CODE}'
                       then t.wttrdfin else 0 end) as care_weight
            from {FACT_TRIP} t
            join {DIM} d on d.houseid = t.houseid and d.personid = t.personid and d.is_current
            where {include}
            group by 1 order by 1
            """
        ).fetchall()
        for sex_code, trips_n, trip_weight, care_weight in rows:
            suppressed = trips_n < SUPPRESS_N
            value = None if suppressed else care_weight / trip_weight
            if scenario == "all_completed" and value is not None:
                baseline[sex_code] = value
            delta = value - baseline[sex_code] if value is not None and sex_code in baseline else None
            out.append(
                base
                | {
                    "measure": "care_trip_share",
                    "scenario": scenario,
                    "sex_code": sex_code,
                    "persons_n": "",
                    "person_weight": "",
                    "trips_n": trips_n,
                    "trip_weight": f"{trip_weight:.1f}",
                    "care_weight": f"{care_weight:.1f}",
                    "value": "" if value is None else f"{value:.6f}",
                    "suppressed": suppressed,
                    "delta_vs_all_completed": ("" if delta is None or scenario == "all_completed" else f"{delta:.6f}"),
                }
            )
    return out


def _ppr_rows(con, base: dict) -> list[dict]:
    """Returns PPR rows per scenario and group, R9-suppressed below n >= 30 on either grain."""
    out: list[dict] = []
    baseline: dict[str, float] = {}
    for scenario, include, group in SCENARIOS:
        rows = con.execute(
            f"""
            with population as (
                select {group} as sex_code, count(*) as persons_n, sum(f.wtperfin) as person_weight
                from {FACT_PERSON} f
                join {DIM} d on d.houseid = f.houseid and d.personid = f.personid and d.is_current
                where {include}
                group by 1
            ),
            care as (
                select {group} as sex_code, count(*) as care_n, sum(t.wttrdfin) as care_weight
                from {FACT_TRIP} t
                join {DIM} d on d.houseid = t.houseid and d.personid = t.personid and d.is_current
                where ({include}) and (t.whyto = '{CARE_CODE}' or t.whyfrom = '{CARE_CODE}')
                group by 1
            )
            select population.sex_code, persons_n, person_weight,
                   coalesce(care_n, 0), coalesce(care_weight, 0.0)
            from population left join care on care.sex_code = population.sex_code
            order by 1
            """
        ).fetchall()
        person_weight_total = sum(row[2] for row in rows)
        care_weight_total = sum(row[4] for row in rows)
        for sex_code, persons_n, person_weight, care_n, care_weight in rows:
            suppressed = persons_n < SUPPRESS_N or care_n < SUPPRESS_N
            value = None
            if not suppressed and person_weight_total and care_weight_total and person_weight:
                value = (care_weight / care_weight_total) / (person_weight / person_weight_total)
            if scenario == "all_completed" and value is not None:
                baseline[sex_code] = value
            delta = value - baseline[sex_code] if value is not None and sex_code in baseline else None
            out.append(
                base
                | {
                    "measure": "ppr",
                    "scenario": scenario,
                    "sex_code": sex_code,
                    "persons_n": persons_n,
                    "person_weight": f"{person_weight:.1f}",
                    "trips_n": care_n,
                    "trip_weight": "",
                    "care_weight": f"{care_weight:.1f}",
                    "value": "" if value is None else f"{value:.6f}",
                    "suppressed": suppressed,
                    "delta_vs_all_completed": ("" if delta is None or scenario == "all_completed" else f"{delta:.6f}"),
                }
            )
    return out


def _scenario_coverage(con, base: dict) -> list[dict]:
    """Returns excluded/reclassified counts and weight shares — the influence bounds."""
    (
        persons_total_weight,
        imputed_n,
        imputed_weight,
        edited_n,
    ) = con.execute(
        f"""
        select sum(f.wtperfin),
               count(*) filter (where d.sex_source = 'imputed'),
               coalesce(sum(f.wtperfin) filter (where d.sex_source = 'imputed'), 0.0),
               count(*) filter (where d.sex_source = 'edited')
        from {DIM} d
        join {FACT_PERSON} f on f.houseid = d.houseid and f.personid = d.personid
        where d.is_current
        """
    ).fetchone()
    trips_total_weight, imputed_trips_n, imputed_trips_weight = con.execute(
        f"""
        select sum(t.wttrdfin),
               count(*) filter (where d.sex_source = 'imputed'),
               coalesce(sum(t.wttrdfin) filter (where d.sex_source = 'imputed'), 0.0)
        from {FACT_TRIP} t
        join {DIM} d on d.houseid = t.houseid and d.personid = t.personid and d.is_current
        """
    ).fetchone()
    rows = []
    for scenario, reclassified in (("observed_only", 0), ("reported_values", edited_n)):
        rows.append(
            base
            | {
                "scenario": scenario,
                "persons_excluded_n": imputed_n,
                "person_weight_excluded_pct": _pct(imputed_weight, persons_total_weight or 0.0),
                "trips_excluded_n": imputed_trips_n,
                "trip_weight_excluded_pct": _pct(imputed_trips_weight, trips_total_weight or 0.0),
                "persons_reclassified_n": reclassified,
            }
        )
    return rows


def _md_table(rows: list[dict], columns: list[str]) -> str:
    """Renders selected columns of result rows as a github table, showing suppression."""
    body = []
    for row in rows:
        hidden = str(row.get("suppressed")) == "True"
        body.append(["suppressed" if hidden and column == "value" else row[column] for column in columns])
    return tabulate(body, headers=columns, tablefmt="github")


def _summary_markdown(split: list[dict], rates: list[dict], equity: list[dict], coverage: list[dict]) -> str:
    """Renders the self-documenting audit summary."""
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    scenario_lines = [
        "- `all_completed` — baseline: every current person, grouped by the completed code "
        "(reproduces the v_care_trip_share_by_sex / v_ppr semantics).",
        "- `observed_only` — rows with `sex_source = 'imputed'` excluded; edited rows keep the completed code.",
        "- `reported_values` — imputed rows excluded; edited rows grouped by `sex_code_reported`.",
    ]
    return "\n".join(
        [
            f"# {DATASET} imputation sensitivity audit",
            "",
            f"Generated {generated} by `gdgap audit-imputation` — regenerate with "
            "`gdgap build --variant aware && gdgap audit-imputation`. Source: own results.",
            "",
            "Westat completed missing sex values by random hot-deck imputation within adjustment cells "
            "(2017 NHTS Weighting Report, Appendix D). Donor assignments are not published, so individual "
            "imputations cannot be reconstructed or validated: this is an imputation sensitivity audit, "
            "not a bias detector. Published weights were raked with the completed sex, so scenario "
            "estimates are sensitivity scenarios under the published weights — never re-raked estimators.",
            "",
            "## Scenarios (frozen definitions)",
            "",
            *scenario_lines,
            "",
            "## Provenance split",
            "",
            _md_table(split, ["sex_source", "persons_n", "persons_pct", "trips_n", "trips_pct", "trip_weight_pct"]),
            "",
            "## Non-reported rates by completed code and age band",
            "",
            "Numerators below n = 30 are flagged unstable — statistical instability, not exposure; "
            "equity cells below n = 30 stay suppressed per R9.",
            "",
            _md_table(
                rates,
                [
                    "dimension",
                    "category",
                    "persons_n",
                    "imputed_n",
                    "imputed_rate_pct",
                    "imputed_unstable",
                    "edited_n",
                    "edited_rate_pct",
                ],
            ),
            "",
            "## Equity measures by scenario",
            "",
            _md_table(
                equity,
                ["measure", "scenario", "sex_code", "trips_n", "persons_n", "value", "delta_vs_all_completed"],
            ),
            "",
            "## Scenario coverage (influence bounds)",
            "",
            _md_table(
                coverage,
                [
                    "scenario",
                    "persons_excluded_n",
                    "person_weight_excluded_pct",
                    "trips_excluded_n",
                    "trip_weight_excluded_pct",
                    "persons_reclassified_n",
                ],
            ),
            "",
            "Share-type scenario deltas are bounded above by the excluded trip-weight share.",
            "",
        ]
    )


def audit_imputation(root: Path | None = None) -> list[Path]:
    """
    Emits the imputation sensitivity audit for the aware build and returns the written paths.

    Deterministic regeneration: CSVs carry snapshot and commit columns and fixed float
    formats, never timestamps; only the markdown summary records its generation time.
    """
    root = root or find_root()
    commit = _git_commit(root)
    with _chdir(root), closing(_connect(root)) as con:
        aware_ready = con.execute(
            "select count(*) from duckdb_tables() where database_name = 'lake' "
            "and schema_name = 'aware' and table_name = 'dim_person_sex'"
        ).fetchone()[0]
        if not aware_ready:
            raise click.ClickException("lake.aware.dim_person_sex is missing — run 'gdgap build --variant aware' first")
        snapshot = con.execute("select max(snapshot_id) from lake.snapshots()").fetchone()[0]
        base = {"snapshot": snapshot, "git_commit": commit}
        split = _provenance_split(con, base)
        rates = _imputation_rates(con, base)
        equity = _care_share_rows(con, base) + _ppr_rows(con, base)
        coverage = _scenario_coverage(con, base)
    out_dir = root / SENSITIVITY_DIR
    _write_csv(out_dir / "provenance_split.csv", SPLIT_FIELDS, split)
    _write_csv(out_dir / "imputation_rates.csv", RATE_FIELDS, rates)
    _write_csv(out_dir / "equity_sensitivity.csv", EQUITY_FIELDS, equity)
    _write_csv(out_dir / "scenario_coverage.csv", COVERAGE_FIELDS, coverage)
    (out_dir / SUMMARY_FILE).write_text(_summary_markdown(split, rates, equity, coverage), encoding="utf-8")
    written = [
        SENSITIVITY_DIR / "provenance_split.csv",
        SENSITIVITY_DIR / "imputation_rates.csv",
        SENSITIVITY_DIR / "equity_sensitivity.csv",
        SENSITIVITY_DIR / "scenario_coverage.csv",
        SENSITIVITY_DIR / SUMMARY_FILE,
    ]
    for path in written:
        click.echo(f"  wrote {path.as_posix()}")
    suppressed_n = sum(1 for row in equity if row["suppressed"])
    click.echo(
        f"✓ Imputation sensitivity audit: {len(equity)} scenario row(s), {suppressed_n} suppressed — "
        "sensitivity scenarios under published weights, not re-raked estimators"
    )
    return written
