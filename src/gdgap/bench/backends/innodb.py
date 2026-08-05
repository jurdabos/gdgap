"""
InnoDB backend: the row-oriented foil, reached over PyMySQL.

The connection comes from the GDGAP_MYSQL_URL environment variable (loaded from .env via
python-dotenv), e.g. mysql+pymysql://root:password@127.0.0.1:3307 for the compose-managed
MySQL container (ADR-0008) — credentials never live in the repo. The mirrored views
require MySQL 8.0.19+ (window functions and CTEs in views).
"""

import os
import socket
from pathlib import Path
from urllib.parse import unquote, urlparse

import click
import pymysql
from dotenv import load_dotenv

CONNECT_TIMEOUT_S = 10


def _endpoint(root: Path) -> tuple:
    """
    Returns (parsed_url, host, port) for the configured MySQL endpoint.

    Loads .env from the given root first; never logs or embeds credentials.
    """
    load_dotenv(root / ".env")
    url = os.environ.get("GDGAP_MYSQL_URL")
    if not url:
        raise click.ClickException(
            "GDGAP_MYSQL_URL is not set — put e.g. mysql+pymysql://root:password@127.0.0.1:3307 into .env"
        )
    parsed = urlparse(url)
    return parsed, parsed.hostname or "127.0.0.1", parsed.port or 3306


class InnodbBackend:
    """Runs SQL against a MySQL/InnoDB server configured via GDGAP_MYSQL_URL."""

    name = "innodb"

    def __init__(self, root: Path):
        self.root = root
        parsed, self.host, self.port = _endpoint(root)
        try:
            self.con = pymysql.connect(
                host=self.host,
                port=self.port,
                user=unquote(parsed.username or ""),
                password=unquote(parsed.password or ""),
                autocommit=True,
                connect_timeout=CONNECT_TIMEOUT_S,
            )
        except pymysql.MySQLError as exc:
            raise click.ClickException(f"cannot connect to MySQL at {self.host}:{self.port} — {exc}") from exc

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


def diagnose(root: Path) -> dict:
    """
    Returns sanitized connectivity facts for the configured MySQL endpoint.

    The dict never contains username, password, query parameters, or the full URL;
    failures are reduced to an error class plus MySQL error code (ADR-0008).
    """
    facts: dict = {
        "configured_endpoint": None,
        "tcp_reachable": False,
        "auth_ok": False,
        "server_version": None,
        "error": None,
    }
    try:
        parsed, host, port = _endpoint(root)
    except click.ClickException as exc:
        facts["error"] = exc.message
        return facts
    facts["configured_endpoint"] = f"{host}:{port}"
    try:
        socket.create_connection((host, port), timeout=3).close()
        facts["tcp_reachable"] = True
    except OSError as exc:
        facts["error"] = f"tcp: {exc.__class__.__name__}: {exc}"
        return facts
    try:
        con = pymysql.connect(
            host=host,
            port=port,
            user=unquote(parsed.username or ""),
            password=unquote(parsed.password or ""),
            connect_timeout=CONNECT_TIMEOUT_S,
        )
        try:
            with con.cursor() as cursor:
                cursor.execute("select version()")
                facts["server_version"] = str(cursor.fetchone()[0])
        finally:
            con.close()
        facts["auth_ok"] = True
    except pymysql.MySQLError as exc:
        code = exc.args[0] if exc.args else "?"
        facts["error"] = f"mysql: {exc.__class__.__name__} (code {code})"
    return facts
