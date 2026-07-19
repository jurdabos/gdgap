"""Integration tests for publishing the dataset schema into a second DuckLake."""

import csv
from contextlib import closing
from pathlib import Path

import duckdb

from gdgap.ingest import nhts2017

PUB_ATTACH = "ATTACH 'ducklake:catalog/pub.ducklake' AS pub_lake (DATA_PATH 'data/pub/')"


def _connect_with_pub(root: Path) -> duckdb.DuckDBPyConnection:
    """Opens a connection with the local lake and a second local ducklake attached as pub_lake."""
    con = duckdb.connect()
    con.execute((root / "sql" / "00_attach.sql").read_text(encoding="utf-8"))
    con.execute(PUB_ATTACH)
    return con


def test_publish_mirrors_dataset_schema(lake_root):
    """Publishes on first run, skips on rerun, republishes under force, verifying each table."""
    nhts2017.ingest(root=lake_root)
    (lake_root / "data" / "pub").mkdir()

    def connect():
        return _connect_with_pub(lake_root)

    first = nhts2017.publish(root=lake_root, target="pub_lake", connect=connect)
    assert [row["action"] for row in first] == ["published"] * 4
    second = nhts2017.publish(root=lake_root, target="pub_lake", connect=connect)
    assert [row["action"] for row in second] == ["skipped"] * 4
    third = nhts2017.publish(root=lake_root, target="pub_lake", force=True, connect=connect)
    assert [row["action"] for row in third] == ["republished"] * 4
    with nhts2017._chdir(lake_root), closing(connect()) as con:
        rows = con.execute(
            "select schema_name, table_name from duckdb_tables() where database_name = 'pub_lake' order by table_name"
        ).fetchall()
    assert rows == [("nhts2017", table) for table in sorted(nhts2017.TABLES)]
    with open(lake_root / nhts2017.PUBLISH_LOG, newline="", encoding="utf-8") as handle:
        logged = list(csv.DictReader(handle))
    assert len(logged) == 12
    assert {row["target"] for row in logged} == {"pub_lake"}


def test_publish_maintain_expires_snapshots(lake_root):
    """Retains only the current snapshot on the target after a maintained publish."""
    nhts2017.ingest(root=lake_root)
    (lake_root / "data" / "pub").mkdir()

    def connect():
        return _connect_with_pub(lake_root)

    nhts2017.publish(root=lake_root, target="pub_lake", connect=connect)
    nhts2017.publish(root=lake_root, target="pub_lake", force=True, connect=connect)
    nhts2017.publish(root=lake_root, target="pub_lake", maintain=True, connect=connect)
    with nhts2017._chdir(lake_root), closing(connect()) as con:
        snapshots = con.execute("select count(*) from pub_lake.snapshots()").fetchone()[0]
        n = con.execute("select count(*) from pub_lake.nhts2017.perpub").fetchone()[0]
    assert snapshots == 1
    assert n == 3


def test_ensure_placement_repairs_misplaced_table(lake_root):
    """Moves a table that landed in the wrong target schema back into the dataset schema."""
    nhts2017.ingest(root=lake_root)
    (lake_root / "data" / "pub").mkdir()
    with nhts2017._chdir(lake_root):
        with closing(_connect_with_pub(lake_root)) as con:
            con.execute("create schema if not exists pub_lake.nhts2017")
            # Simulating the observed MotherDuck glitch: the table lands in main instead
            con.execute("create table pub_lake.main.hhpub as select * from lake.nhts2017.hhpub")

        with closing(_connect_with_pub(lake_root)) as vcon:
            nhts2017._ensure_placement(vcon, "pub_lake", "hhpub", 2)
        with closing(_connect_with_pub(lake_root)) as con:
            schemas = nhts2017._schemas_holding(con, "pub_lake", "hhpub")
            n = con.execute("select count(*) from pub_lake.nhts2017.hhpub").fetchone()[0]
    assert schemas == ["nhts2017"]
    assert n == 2
