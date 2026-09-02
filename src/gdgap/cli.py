"""
Command-line interface for gdgap.

Exposes the lake/warehouse commands (ingest, profile, summarize, publish,
build, bench, validate, audit-imputation, mysql-doctor) plus the canonical
``push`` workflow, which is imported from :mod:`acidbase.push` so this repo
shares the a6a ecosystem's hook-aware, DVC-aware behaviour instead of
carrying a divergent copy of it.
"""

import json

import click
from acidbase.cli_utils import group
from acidbase.push import push_command
from acidbase.versioning import bump_command


@group()
def cli() -> None:
    """Lake and warehouse tooling for the gdgap study."""


# The canonical ``push`` workflow lives in :mod:`acidbase.push`; mounting it
# here keeps gdgap in step with every other consumer repo.
cli.add_command(bump_command)
cli.add_command(push_command)


@cli.command("ingest")
@click.argument("dataset", default="nhts2017", required=False)
@click.option("--force", is_flag=True, help="Drop and recreate existing lake tables")
def ingest_cmd(dataset: str, force: bool) -> None:
    """Ingests a registered dataset into the DuckLake (manifest-verified, idempotent)."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.ingest import nhts2017

    if dataset != nhts2017.DATASET:
        raise click.BadParameter(f"unknown dataset '{dataset}'; registered: {nhts2017.DATASET}")
    nhts2017.ingest(force=force)


@cli.command("profile")
def profile_cmd() -> None:
    """Emits the W1 profiling CSVs into results/profile/."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.ingest import nhts2017

    nhts2017.profile()


@cli.command("summarize")
def summarize_cmd() -> None:
    """Renders the profile summary table (thesis 3.2) from the profiling CSVs."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.ingest import nhts2017

    nhts2017.summarize()


@cli.command("publish")
@click.option("--target", default="gdgap_lake", show_default=True, help="MotherDuck DuckLake database name")
@click.option("--force", is_flag=True, help="Drop and republish tables that already exist on the target")
@click.option("--maintain", is_flag=True, help="Expire old snapshots and clean up files on the target afterwards")
def publish_cmd(target: str, force: bool, maintain: bool) -> None:
    """Mirrors the local lake's dataset schema into a MotherDuck-hosted DuckLake."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.ingest import nhts2017

    nhts2017.publish(target=target, force=force, maintain=maintain)


@cli.command("build")
@click.option("--variant", type=click.Choice(["blind", "aware"]), required=True, help="Warehouse variant to build")
@click.option(
    "--backend",
    type=click.Choice(["ducklake", "innodb"]),
    default="ducklake",
    show_default=True,
    help="Execution backend (innodb is the row-oriented foil)",
)
def build_cmd(variant: str, backend: str) -> None:
    """Builds one warehouse variant from the lake, enforcing the R-number header gate."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.build import build

    build(variant=variant, backend_name=backend)


@cli.command("bench")
@click.option(
    "--backend",
    type=click.Choice(["ducklake", "innodb"]),
    default="ducklake",
    show_default=True,
    help="Execution backend (innodb is the row-oriented foil)",
)
@click.option("--variant", type=click.Choice(["blind", "aware"]), required=True, help="Warehouse variant to bench")
@click.option(
    "--temperature",
    type=click.Choice(["warm"]),
    default="warm",
    show_default=True,
    help="Cache protocol; cold stays rejected until its reset method has an ADR (ADR-0004)",
)
@click.option(
    "--repetitions",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Recorded repetitions per query (evidence runs use >= 5 per ADR-0004)",
)
@click.option("--seed", type=int, default=None, help="Query-order shuffle seed (generated and persisted when omitted)")
@click.option("--skip-storage", is_flag=True, help="Skip the storage-cost measurement pass")
def bench_cmd(
    backend: str, variant: str, temperature: str, repetitions: int, seed: int | None, skip_storage: bool
) -> None:
    """Runs the ADR-0004 warm benchmark protocol for one backend/variant matrix cell."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.bench.run import run_bench

    run_bench(
        backend_name=backend,
        variant=variant,
        temperature=temperature,
        repetitions=repetitions,
        seed=seed,
        skip_storage=skip_storage,
    )


@cli.command("bench2")
@click.option(
    "--backend",
    type=click.Choice(["ducklake", "innodb"]),
    default="ducklake",
    show_default=True,
    help="Execution backend (innodb is the row-oriented foil)",
)
@click.option(
    "--condition",
    type=click.Choice(["d0", "c1", "c2", "c3"]),
    default=None,
    help="ADR-0011 condition (default: d0 for ducklake, c1 for innodb); c2 needs the compose pool knob",
)
@click.option(
    "--workload",
    type=click.Choice(["agn", "eq", "both"]),
    default="both",
    show_default=True,
    help="W_agn runs on both variants; W_eq is aware-only (ADR-0011)",
)
@click.option("--blocks", type=click.IntRange(min=1), default=4, show_default=True, help="Counterbalanced blocks")
@click.option(
    "--reps",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="Recorded repetitions per segment (2 segments per variant per block)",
)
@click.option("--bootstrap-seed", type=int, default=None, help="Bootstrap seed (generated and persisted when omitted)")
@click.option("--allow-small", is_flag=True, help="Skip the full-scale guard (fixture-scale test runs only)")
@click.option("--summarize-only", is_flag=True, help="Only regenerate results/bench2/summary.csv from retained rows")
def bench2_cmd(
    backend: str,
    condition: str | None,
    workload: str,
    blocks: int,
    reps: int,
    bootstrap_seed: int | None,
    allow_small: bool,
    summarize_only: bool,
) -> None:
    """Runs the ADR-0011 mechanism-probe protocol (bench v2) for one backend/condition cell."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.bench.run2 import regenerate_summary2, run_bench2
    from gdgap.ingest.nhts2017 import find_root

    if summarize_only:
        path = regenerate_summary2(find_root())
        click.echo(f"✓ Summary regenerated at {path}")
        return
    run_bench2(
        backend_name=backend,
        condition=condition,
        workload=workload,
        blocks=blocks,
        reps=reps,
        bootstrap_seed=bootstrap_seed,
        allow_small=allow_small,
    )


@cli.command("validate")
@click.argument("dataset", default="nhts2017", required=False)
@click.option(
    "--stage",
    type=click.Choice(["ingest", "aware-build", "all"]),
    default="all",
    show_default=True,
    help="Pipeline stage(s) to validate",
)
@click.option(
    "--backend",
    type=click.Choice(["ducklake", "innodb"]),
    default="ducklake",
    show_default=True,
    help="Backend to validate (ingest rules run on the lake only)",
)
def validate_cmd(dataset: str, stage: str, backend: str) -> None:
    """Runs the R13 data-quality contract and appends rule-level conformance evidence (ADR-0009)."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.quality import validate

    stages = {"ingest": ["ingest"], "aware-build": ["aware_build"], "all": ["ingest", "aware_build"]}[stage]
    if backend == "innodb":
        stages = [item for item in stages if item != "ingest"]
        if not stages:
            raise click.BadParameter("the ingest stage validates the lake — use --backend ducklake")
    for item in stages:
        validate(dataset=dataset, stage=item, backend_name=backend)


@cli.command("audit-imputation")
def audit_imputation_cmd() -> None:
    """Emits the imputation sensitivity audit (provenance split, rates, scenario deltas) for the aware build."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.sensitivity import audit_imputation

    audit_imputation()


@cli.command("mysql-doctor")
@click.option("--json", "as_json", is_flag=True, help="Emit the sanitized facts as JSON")
def mysql_doctor_cmd(as_json: bool) -> None:
    """Diagnoses MySQL connectivity with sanitized output — never credentials or the full URL (ADR-0008)."""
    # Importing lazily so push invocations skip the duckdb import
    from gdgap.bench.backends.innodb import diagnose
    from gdgap.ingest.nhts2017 import find_root

    facts = diagnose(find_root())
    if as_json:
        click.echo(json.dumps(facts, indent=2, sort_keys=True))
    else:
        click.echo(f"Configured endpoint: {facts['configured_endpoint'] or 'not configured'}")
        click.echo(f"TCP reachable: {'yes' if facts['tcp_reachable'] else 'no'}")
        click.echo(f"MySQL authentication: {'yes' if facts['auth_ok'] else 'no'}")
        click.echo(f"MySQL version: {facts['server_version'] or 'n/a'}")
        if facts["error"]:
            click.echo(f"Error: {facts['error']}")
    if facts["error"]:
        raise SystemExit(1)


def main() -> None:
    """Entry point for the CLI."""
    cli()
