"""Integration tests for the Phase D variant builds on the DuckLake backend."""

import os
from pathlib import Path

import duckdb
import pytest

from gdgap import build as build_module
from gdgap.ingest import nhts2017

requires_mysql = pytest.mark.skipif(not os.environ.get("GDGAP_MYSQL_URL"), reason="GDGAP_MYSQL_URL not set")


def _lake_query(root: Path, sql: str) -> list[tuple]:
    """Runs one query against the fixture lake on a fresh connection."""
    with nhts2017._chdir(root):
        con = duckdb.connect()
        con.execute((root / "sql" / "00_attach.sql").read_text(encoding="utf-8"))
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()


def test_build_blind_creates_queryable_warehouse(lake_root):
    """Builds the blind variant: facts without sex, total-only care share."""
    nhts2017.ingest(root=lake_root)
    summary = build_module.build("blind", root=lake_root)
    assert summary["files"] == ["01_fact_person.sql", "02_fact_trip.sql", "03_v_measures.sql"]
    assert summary["r_coverage"] == ["R2", "R7", "R11"]
    assert _lake_query(lake_root, "select count(*) from lake.blind.fact_person")[0][0] == 3
    assert _lake_query(lake_root, "select count(*) from lake.blind.fact_trip")[0][0] == 2
    care_share = _lake_query(lake_root, "select care_trip_share from lake.blind.v_care_trip_share")[0][0]
    # Both fixture trips touch the care code '06', so the total share is 1.0
    assert care_share == pytest.approx(1.0)
    columns = {row[0] for row in _lake_query(lake_root, "describe lake.blind.fact_person")}
    assert "sex_code" not in columns


def test_build_aware_dimension_and_measures(lake_root):
    """Builds the aware variant: distinct code domains, Type-2-style dimension with provenance, equity views."""
    nhts2017.ingest(root=lake_root)
    summary = build_module.build("aware", root=lake_root)
    assert summary["r_coverage"] == ["R1", "R2", "R3", "R6", "R7", "R8", "R9", "R11"]
    assert _lake_query(lake_root, "select count(*) from lake.aware.dim_sex_code")[0][0] == 5
    assert _lake_query(lake_root, "select count(*) from lake.aware.dim_gender_identity_code")[0][0] == 5
    # Sex and gender identity stay distinct domains: no gender concept in the sex list, and
    # extension rows never claim a standard source (ADR-0006)
    sex_codes = {row[0] for row in _lake_query(lake_root, "select sex_code from lake.aware.dim_sex_code")}
    assert "X" not in sex_codes
    mislabelled = _lake_query(
        lake_root,
        "select count(*) from lake.aware.dim_sex_code where is_extension and source_standard like '%ISO%'",
    )[0][0]
    assert mislabelled == 0
    # NHTS 2017 collects no gender identity: the attribute exhibits non-collection by construction
    assert _lake_query(lake_root, "select distinct gender_identity_code from lake.aware.dim_person_sex") == [("NC",)]
    sources = dict(_lake_query(lake_root, "select sex_source, count(*) from lake.aware.dim_person_sex group by 1"))
    assert sources == {"reported": 2, "imputed": 1}
    imputation = dict(_lake_query(lake_root, "select sex_source, persons from lake.aware.v_sex_imputation_share"))
    assert imputation == {"reported": 2, "imputed": 1}
    # The n >= 30 small-cell suppression (R9) blanks the equity views on the tiny fixture
    assert _lake_query(lake_root, "select * from lake.aware.v_ppr") == []
    assert _lake_query(lake_root, "select * from lake.aware.v_care_trip_share_by_sex") == []


def test_build_refuses_unregistered_ddl(lake_root):
    """Aborts before executing anything when a DDL file lacks a valid R-header."""
    rogue = lake_root / "sql" / "ddl" / "blind" / "99_rogue.sql"
    rogue.write_text("select 1;\n", encoding="utf-8")
    with pytest.raises(Exception, match="R-number header"):
        build_module.build("blind", root=lake_root)


@requires_mysql
def test_build_innodb_mirrors_lake(lake_root):
    """Builds the InnoDB foil and verifies copied row counts (needs GDGAP_MYSQL_URL)."""
    from gdgap.bench.backends.innodb import InnodbBackend

    nhts2017.ingest(root=lake_root)
    build_module.build("aware", root=lake_root)
    build_module.build("aware", backend_name="innodb", root=lake_root)
    backend = InnodbBackend(lake_root)
    try:
        assert backend.fetchall("select count(*) from gdgap_aware.dim_person_sex")[0][0] == 3
        assert backend.fetchall("select count(*) from gdgap_aware.fact_trip")[0][0] == 2
    finally:
        backend.close()
