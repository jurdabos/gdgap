"""
InnoDB backend: the row-oriented foil, reached over PyMySQL.

The connection comes from the GDGAP_MYSQL_URL environment variable (loaded from .env via
python-dotenv), e.g. mysql+pymysql://user:password@127.0.0.1:3306 — credentials never live
in the repo. The mirrored views require MySQL 8.0.19+ (window functions and CTEs in views).
"""

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import click
import pymysql
from dotenv import load_dotenv


class InnodbBackend:
    """Runs SQL against a MySQL/InnoDB server configured via GDGAP_MYSQL_URL."""

    name = "innodb"

    def __init__(self, root: Path):
        self.root = root
        load_dotenv(root / ".env")
        url = os.environ.get("GDGAP_MYSQL_URL")
        if not url:
            raise click.ClickException(
                "GDGAP_MYSQL_URL is not set — put e.g. mysql+pymysql://user:password@127.0.0.1:3306 into .env"
            )
        parsed = urlparse(url)
        try:
            self.con = pymysql.connect(
                host=parsed.hostname or "127.0.0.1",
                port=parsed.port or 3306,
                user=unquote(parsed.username or ""),
                password=unquote(parsed.password or ""),
                autocommit=True,
            )
        except pymysql.MySQLError as exc:
            raise click.ClickException(
                f"cannot connect to MySQL at {parsed.hostname}:{parsed.port or 3306} — {exc}"
            ) from exc

    def ensure_target(self, variant: str) -> None:
        """Creates the variant database when missing."""
        self.execute(f"create database if not exists gdgap_{variant}")

    @staticmethod
    def split_statements(script: str) -> list[str]:
        """Splits a SQL script into statements at line-final semicolons, dropping comment-only chunks."""
        statements: list[str] = []
        buffer: list[str] = []
        for line in script.splitlines():
            buffer.append(line)
            if line.rstrip().endswith(";"):
                statement = "\n".join(buffer).strip()
                buffer = []
                code_lines = [ln for ln in statement.splitlines() if not ln.strip().startswith("--")]
                if any(ln.strip() for ln in code_lines):
                    statements.append(statement)
        return statements

    def run_sql_file(self, path: Path) -> None:
        """Executes a SQL script file statement by statement."""
        for statement in self.split_statements(path.read_text(encoding="utf-8")):
            self.execute(statement)

    def execute(self, sql: str) -> None:
        """Executes a single statement."""
        with self.con.cursor() as cursor:
            cursor.execute(sql)

    def fetchall(self, sql: str) -> list[tuple]:
        """Returns all rows for a query."""
        with self.con.cursor() as cursor:
            cursor.execute(sql)
            return list(cursor.fetchall())

    def insert_rows(self, table: str, columns: list[str], rows: list[tuple]) -> int:
        """Inserts a batch of rows and returns the inserted count."""
        if not rows:
            return 0
        placeholders = ", ".join(["%s"] * len(columns))
        column_list = ", ".join(columns)
        with self.con.cursor() as cursor:
            cursor.executemany(f"insert into {table} ({column_list}) values ({placeholders})", rows)
        return len(rows)

    def close(self) -> None:
        """Closes the connection."""
        self.con.close()
