import logging
import time
from urllib.parse import parse_qs, unquote, urlsplit

import pymssql
from flask import current_app, g

log = logging.getLogger(__name__)

# pymssql error numbers that mean "the database is not ready yet, try again soon".
# 40613: the Azure SQL database is not available, for example while it resumes from a pause.
# 20002 and 20003: the connection failed or timed out (they also happen while it resumes).
RETRYABLE_ERRORS = {40613, 20002, 20003}

# Seconds to wait before each new try. At startup the service waits about two
# minutes in total, because a paused Azure SQL database takes about one to resume.
# A request only retries twice, so it never hangs for long.
STARTUP_RETRY_DELAYS = (2, 4, 8, 15, 15, 15, 15, 15, 15, 15)
REQUEST_RETRY_DELAYS = (1, 2)


def parse_database_url(url):
    """Split "mssql://user:password@host:1433/database" into pymssql's arguments.

    The user name and password may contain URL-escaped characters
    (for example %40 for @), so they are unescaped here.
    Azure SQL only accepts encrypted connections, so there the URL ends with
    "?encrypt=true". Compose's SQL Server leaves it off.
    """
    parts = urlsplit(url or "")
    if parts.scheme != "mssql" or not parts.hostname or not parts.path.strip("/"):
        raise ValueError("DATABASE_URL must look like mssql://user:password@host:1433/database")
    settings = {
        "server": parts.hostname,
        "port": parts.port or 1433,
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": parts.path.strip("/"),
    }
    if parse_qs(parts.query).get("encrypt") == ["true"]:
        settings["encryption"] = "require"  # refuse to connect without encryption
    return settings


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


def is_retryable(error):
    """True if the error only means the database is not ready yet."""
    # pymssql puts (error number, message) in the error's first argument.
    details = error.args[0] if error.args else None
    return isinstance(details, tuple) and details[0] in RETRYABLE_ERRORS


def connect(database_url, retry_delays=(), **options):
    """Open a connection. Every statement runs inside a transaction until commit().

    If the database is not ready yet, wait retry_delays[0] seconds and try
    again, then retry_delays[1], and so on. Any other error, or the last one,
    is raised straight away. With no delays there is only one try.
    options go straight to pymssql, e.g. login_timeout=5 (seconds to wait
    for the server) or timeout=5 (seconds a query may take).
    """
    settings = parse_database_url(database_url)
    for delay in retry_delays:
        try:
            return Connection(pymssql.connect(**settings, autocommit=False, **options))
        except pymssql.OperationalError as error:
            if not is_retryable(error):
                raise
            log.warning("database is not ready yet (%s), trying again in %ss", error.args[0][0], delay)
            time.sleep(delay)
    return Connection(pymssql.connect(**settings, autocommit=False, **options))


def get_db():
    """Return this request's connection, opening it on first use."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE_URL"], retry_delays=REQUEST_RETRY_DELAYS)
    return g.db


def close_db(error=None):
    """Close this request's connection. Flask calls this after every request.

    Anything not committed is rolled back when the connection closes.
    """
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
