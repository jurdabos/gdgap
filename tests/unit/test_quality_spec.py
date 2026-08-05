"""Unit tests for the R13 data-quality specification and its loader (ADR-0009)."""

import json
from pathlib import Path

import click
import pytest

from gdgap import quality
from gdgap.build import registry_ids

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_spec_loads_and_declares_sections():
    """Loads the shipped nhts2017 spec with its purpose/syntax/semantics/pragmatics declarations."""
    spec = quality.load_spec(REPO_ROOT, "nhts2017")
    assert spec["dataset"] == "nhts2017"
    for section in ("purpose", "syntax", "semantics", "pragmatics"):
        assert section in spec
    assert spec["rules"]


def test_rule_ids_unique_and_patterned():
    """Keeps rule IDs unique and within the DQ-(SYN|SEM|PRAG)-NN contract."""
    spec = quality.load_spec(REPO_ROOT, "nhts2017")
    ids = [rule["rule_id"] for rule in spec["rules"]]
    assert len(ids) == len(set(ids))
    for rule_id in ids:
        assert quality.RULE_ID_PATTERN.match(rule_id), rule_id


def test_rules_use_declared_vocabularies():
    """Restricts every rule to the declared stages, severities, backends, and check types."""
    spec = quality.load_spec(REPO_ROOT, "nhts2017")
    for rule in spec["rules"]:
        assert rule["stage"] in quality.STAGES
        assert rule["severity"] in quality.SEVERITIES
        assert rule["backends"] and set(rule["backends"]) <= set(quality.BACKENDS)
        assert rule["check"]["type"] in quality.CHECK_TYPES


def test_rule_r_ids_exist_in_registry():
    """Makes the traceability executable both ways: every rule links a registered R-number."""
    spec = quality.load_spec(REPO_ROOT, "nhts2017")
    valid = registry_ids(REPO_ROOT)
    for rule in spec["rules"]:
        assert rule["r_id"] in valid, rule["rule_id"]


def test_datasets_with_specs_discovers_nhts2017():
    """Finds the shipped spec through the registry-plane discovery used by the build hook."""
    assert "nhts2017" in quality.datasets_with_specs(REPO_ROOT)


def test_load_spec_requires_file(tmp_path):
    """Fails with an R13 hint when a dataset has no spec."""
    with pytest.raises(click.ClickException, match="DATA_QUALITY_SPEC"):
        quality.load_spec(tmp_path, "nhts2017")


def test_load_spec_rejects_malformed(tmp_path):
    """Names the problems of a malformed spec instead of running it."""
    path = tmp_path / "datasets" / "x" / "DATA_QUALITY_SPEC.json"
    path.parent.mkdir(parents=True)
    rogue = {
        "dataset": "x",
        "rules": [
            {
                "rule_id": "DQ-BAD-1",
                "r_id": "R7",
                "stage": "nightly",
                "severity": "fatal",
                "backends": ["oracle"],
                "description": "malformed on purpose",
                "check": {"type": "sql_scalar"},
                "evidence": "nowhere",
            }
        ],
    }
    path.write_text(json.dumps(rogue), encoding="utf-8")
    with pytest.raises(click.ClickException, match="invalid data-quality spec"):
        quality.load_spec(tmp_path, "x")
