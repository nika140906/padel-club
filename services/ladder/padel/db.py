from urllib.parse import unquote, urlsplit

import pymssql
from flask import current_app, g


def parse_database_url(url):
    """Split "mssql://user:password@host:1433/database" into pymssql's arguments.

    The user name and password may contain URL-escaped characters
    (for example %40 for @), so they are unescaped here.
    """
    parts = urlsplit(url or "")
    if parts.scheme != "mssql" or not parts.hostname or not parts.path.strip("/"):
        raise ValueError("DATABASE_URL must look like mssql://user:password@host:1433/database")
    return {
        "server": parts.hostname,
        "port": parts.port or 1433,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": parts.path.strip("/"),
    }


class Connection:
    """A thin wrapper around a pymssql connection.

    It keeps the service code short: conn.execute(sql, params) runs a query
    and returns a cursor whose rows are dicts, read by column name.
    pymssql uses %s as the placeholder for parameters.
    """

    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=None):
        cursor = self.raw.cursor(as_dict=True)
        cursor.execute(sql, params)
        return cursor

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()


def connect(database_url, **options):
    """Open a connection. Every statement runs inside a transaction until commit().

    options go straight to pymssql, e.g. login_timeout=5 (seconds to wait
    for the server) or timeout=5 (seconds a query may take).
    """
    return Connection(
        pymssql.connect(**parse_database_url(database_url), autocommit=False, **options)
    )


def get_db():
    """Return this request's connection, opening it on first use."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_URL"])
    return g.db


def close_db(error=None):
    """Close this request's connection. Flask calls this after every request.

    Anything not committed is rolled back when the connection closes.
    """
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
