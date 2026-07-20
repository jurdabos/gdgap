"""DuckLake backend: the canonical columnar engine, attached per sql/00_attach.sql."""

from pathlib import Path

import duckdb

ATTACH_SQL = Path("sql/00_attach.sql")


class DucklakeBackend:
    """Runs SQL against the local DuckLake with the lake catalog attached."""

    name = "ducklake"

    def __init__(self, root: Path):
        self.root = root
        self.con = duckdb.connect()
        self.con.execute((root / ATTACH_SQL).read_text(encoding="utf-8"))

    def ensure_target(self, variant: str) -> None:
        """Creates the variant schema when missing."""
        self.con.execute(f"create schema if not exists lake.{variant}")

    def run_sql_file(self, path: Path) -> None:
        """Executes a SQL script file as a whole."""
        self.con.execute(path.read_text(encoding="utf-8"))

    def execute(self, sql: str) -> None:
        """Executes a single statement."""
        self.con.execute(sql)

    def fetchall(self, sql: str) -> list[tuple]:
        """Returns all rows for a query."""
        return self.con.execute(sql).fetchall()

    def list_variant_tables(self, variant: str) -> list[str]:
        """Returns the base-table names of a variant schema in the lake."""
        rows = self.con.execute(
            "select table_name from duckdb_tables() where database_name = 'lake' and schema_name = ? "
            "order by table_name",
            [variant],
        ).fetchall()
        return [row[0] for row in rows]

    def close(self) -> None:
        """Closes the connection."""
        self.con.close()
