"""
R13 data-quality contract: executable conformance of equity-critical data (ADR-0009).

Implements King & Schwarzenbach's specification -> monitoring/control mechanism in the
smallest form that fits a static thesis artefact: a registered dataset may carry a
machine-readable spec (datasets/<dataset>/DATA_QUALITY_SPEC.json) whose rules run
deterministically after ingest and after every aware build, on the backend just built.
Outcomes append to results/quality/<dataset>/conformance.csv; error-severity failures
abort the run while warnings stay visible in the log. Rules are scale-invariant by
design, so the fixture lake and the full dataset satisfy one and the same contract.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import click

from gdgap.bench.backends import get_backend
from gdgap.bench.run import _git_commit, render
from gdgap.ingest.nhts2017 import _append_csv, _chdir, find_root

QUALITY_DIR = Path("results/quality")
STAGES = ("ingest", "aware_build")
SEVERITIES = ("error", "warning")
BACKENDS = ("ducklake", "innodb")
CHECK_TYPES = ("sql_scalar", "sql_executes")
RULE_ID_PATTERN = re.compile(r"^DQ-(SYN|SEM|PRAG)-\d{2}$")
RULE_KEYS = ("rule_id", "r_id", "stage", "severity", "backends", "description", "check", "evidence")
CONFORMANCE_FIELDS = [
    "run_id",
    "ts_utc",
    "git_commit",
    "dataset",
    "stage",
    "backend",
    "snapshot",
    "rule_id",
    "r_id",
    "severity",
    "expected",
    "observed",
    "passed",
    "evidence",
]
_OPS = {
    "eq": lambda observed, expected: observed == expected,
    "lte": lambda observed, expected: observed <= expected,
    "gte": lambda observed, expected: observed >= expected,
}


def spec_path(root: Path, dataset: str) -> Path:
    """Returns the path of a dataset's data-quality specification."""
    return root / "datasets" / dataset / "DATA_QUALITY_SPEC.json"


def datasets_with_specs(root: Path) -> list[str]:
    """Returns the registered datasets that carry a data-quality specification."""
    return sorted(path.parent.name for path in (root / "datasets").glob("*/DATA_QUALITY_SPEC.json"))


def _rule_problems(rule: dict, index: int, seen: set[str]) -> list[str]:
    """Returns the shape problems of one rule entry."""
    label = rule.get("rule_id") or f"rules[{index}]"
    missing = [key for key in RULE_KEYS if key not in rule]
    if missing:
        return [f"{label}: missing key(s) {', '.join(missing)}"]
    problems: list[str] = []
    if not RULE_ID_PATTERN.match(rule["rule_id"]):
        problems.append(f"{label}: rule_id must match DQ-(SYN|SEM|PRAG)-NN")
    if rule["rule_id"] in seen:
        problems.append(f"{label}: duplicate rule_id")
    seen.add(rule["rule_id"])
    if rule["stage"] not in STAGES:
        problems.append(f"{label}: unknown stage {rule['stage']!r}")
    if rule["severity"] not in SEVERITIES:
        problems.append(f"{label}: unknown severity {rule['severity']!r}")
    if not rule["backends"] or not set(rule["backends"]) <= set(BACKENDS):
        problems.append(f"{label}: backends must be a non-empty subset of {BACKENDS}")
    check = rule["check"]
    if not isinstance(check, dict) or check.get("type") not in CHECK_TYPES:
        problems.append(f"{label}: check.type must be one of {CHECK_TYPES}")
    elif check["type"] == "sql_scalar" and (
        "sql" not in check or "expected" not in check or check.get("op", "eq") not in _OPS
    ):
        problems.append(f"{label}: sql_scalar checks need sql, expected, and a known op")
    elif check["type"] == "sql_executes" and "sql_file" not in check:
        problems.append(f"{label}: sql_executes checks need sql_file")
    return problems


def load_spec(root: Path, dataset: str) -> dict:
    """
    Returns the parsed data-quality specification of a dataset, shape-validated.

    Raises ClickException naming every problem when the spec is missing or malformed.
    """
    path = spec_path(root, dataset)
    if not path.is_file():
        raise click.ClickException(
            f"no DATA_QUALITY_SPEC.json for '{dataset}' under datasets/ — R13 requires one per registered dataset"
        )
    spec = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if spec.get("dataset") != dataset:
        problems.append(f"dataset field is {spec.get('dataset')!r}, expected {dataset!r}")
    rules = spec.get("rules")
    if not rules:
        problems.append("rules array is missing or empty")
    seen: set[str] = set()
    for index, rule in enumerate(rules or []):
        problems.extend(_rule_problems(rule, index, seen))
    if problems:
        raise click.ClickException(f"invalid data-quality spec for '{dataset}': " + "; ".join(problems))
    return spec


def _stage_schema(dataset: str, stage: str, backend_name: str) -> str:
    """Returns the physical schema a stage's rules run against on a backend."""
    if stage == "ingest":
        return f"lake.{dataset}"
    return "lake.aware" if backend_name == "ducklake" else "gdgap_aware"


def _snapshot(backend) -> str:
    """Returns the current DuckLake snapshot id; empty for other backends."""
    if backend.name != "ducklake":
        return ""
    return str(backend.fetchall("select max(snapshot_id) from lake.snapshots()")[0][0])


def _run_check(backend, root: Path, check: dict, schema: str) -> tuple[bool, str, str]:
    """Executes one rule check and returns (passed, expected, observed) as log values."""
    if check["type"] == "sql_executes":
        body = (root / check["sql_file"]).read_text(encoding="utf-8")
        try:
            backend.fetchall(render(body, schema))
        except Exception as exc:  # guardrail: a failing probe is a recorded nonconformity, not a crash
            return False, "executes", f"error: {str(exc).replace(chr(10), ' ')[:200]}"
        return True, "executes", "ok"
    op = check.get("op", "eq")
    expected = check["expected"]
    try:
        observed = backend.fetchall(render(check["sql"], schema))[0][0]
    except Exception as exc:  # guardrail: a broken probe target is itself a nonconformity
        return False, f"{op} {expected}", f"error: {str(exc).replace(chr(10), ' ')[:200]}"
    try:
        passed = _OPS[op](float(observed), float(expected))
    except (TypeError, ValueError):
        passed = op == "eq" and str(observed) == str(expected)
    return passed, f"{op} {expected}", str(observed)


def validate(dataset: str, stage: str, backend_name: str = "ducklake", root: Path | None = None) -> list[dict]:
    """
    Runs one stage of a dataset's data-quality contract on one backend (R13, ADR-0009).

    Appends rule-level outcomes to results/quality/<dataset>/conformance.csv, echoes each
    rule, and raises ClickException when any error-severity rule fails; warning-severity
    nonconformities stay visible in the log and the echo only. Returns the appended rows.
    """
    if stage not in STAGES:
        raise click.ClickException(f"unknown stage '{stage}'; expected one of: {', '.join(STAGES)}")
    if backend_name not in BACKENDS:
        raise click.ClickException(f"unknown backend '{backend_name}'; expected one of: {', '.join(BACKENDS)}")
    root = root or find_root()
    spec = load_spec(root, dataset)
    rules = [rule for rule in spec["rules"] if rule["stage"] == stage and backend_name in rule["backends"]]
    if not rules:
        click.echo(f"  R13: no {stage} rules for backend {backend_name} — nothing to validate")
        return []
    started = datetime.now(UTC)
    ts_utc = started.strftime("%Y-%m-%d %H:%M:%S")
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-validate-{dataset}-{stage}-{backend_name}"
    commit = _git_commit(root)
    schema = _stage_schema(dataset, stage, backend_name)
    click.echo(f"R13 conformance — {dataset}/{stage}/{backend_name} against {schema}")
    log_rows: list[dict] = []
    with _chdir(root):
        backend = get_backend(backend_name, root)
        try:
            snapshot = _snapshot(backend)
            for rule in rules:
                passed, expected, observed = _run_check(backend, root, rule["check"], schema)
                log_rows.append(
                    {
                        "run_id": run_id,
                        "ts_utc": ts_utc,
                        "git_commit": commit,
                        "dataset": dataset,
                        "stage": stage,
                        "backend": backend_name,
                        "snapshot": snapshot,
                        "rule_id": rule["rule_id"],
                        "r_id": rule["r_id"],
                        "severity": rule["severity"],
                        "expected": expected,
                        "observed": observed,
                        "passed": passed,
                        "evidence": rule["evidence"],
                    }
                )
                marker = "ok" if passed else f"FAIL ({rule['severity']}) expected {expected}, observed {observed}"
                click.echo(f"  {rule['rule_id']} [{rule['r_id']}]: {marker}")
        finally:
            backend.close()
    conformance = QUALITY_DIR / dataset / "conformance.csv"
    _append_csv(root / conformance, CONFORMANCE_FIELDS, log_rows)
    failed_errors = [row["rule_id"] for row in log_rows if not row["passed"] and row["severity"] == "error"]
    failed_warnings = [row["rule_id"] for row in log_rows if not row["passed"] and row["severity"] == "warning"]
    passed_n = sum(1 for row in log_rows if row["passed"])
    click.echo(
        f"✓ R13 conformance {dataset}/{stage}/{backend_name}: {passed_n}/{len(log_rows)} rule(s) passed — "
        f"evidence appended to {conformance.as_posix()}"
    )
    if failed_warnings:
        click.echo(f"  ⚠ warning-severity nonconformities: {', '.join(failed_warnings)}")
    if failed_errors:
        raise click.ClickException(
            f"R13 conformance failed for {dataset}/{stage}/{backend_name}: {', '.join(failed_errors)} — "
            f"see {conformance.as_posix()}"
        )
    return log_rows
