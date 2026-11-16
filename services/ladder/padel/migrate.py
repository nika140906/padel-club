"""A small migration runner.

Each file in the migrations folder is one migration, named with a number
first ("001_init.sql", "002_add_level.sql"), so sorting the names gives
the order to run them in. The table schema_migrations remembers which ones
already ran, so each migration runs exactly once. Applied files are never
edited: a correction goes in a new file.
"""

import logging
import os
import re

log = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")
FILE_PATTERN = re.compile(r"^\d{3}_[a-z0-9_]+\.sql$")

CREATE_TABLE = """
IF OBJECT_ID(N'schema_migrations', N'U') IS NULL
    CREATE TABLE schema_migrations (
        version    NVARCHAR(255) NOT NULL PRIMARY KEY,
        applied_at DATETIME2(0)  NOT NULL DEFAULT SYSUTCDATETIME()
    );
"""


def migration_files(folder):
    """The migration file names in the order they must run."""
    return sorted(name for name in os.listdir(folder) if FILE_PATTERN.match(name))


def applied_versions(conn):
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def migrate(conn, folder=MIGRATIONS_DIR):
    """Run every migration that has not run yet and return their names."""
    conn.execute(CREATE_TABLE)
    conn.commit()

    done = applied_versions(conn)
    newly_applied = []
    for name in migration_files(folder):
        if name in done:
            continue
        with open(os.path.join(folder, name), encoding="utf-8") as file:
            sql = file.read()
        # The migration and its schema_migrations row are saved in one
        # transaction: if any statement fails, nothing of it is kept and
        # it will be tried again on the next start.
        try:
            conn.execute(sql)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (name,))
            conn.commit()
        except Exception:
            conn.rollback()
            log.error("migration %s failed, nothing was changed", name)
            raise
        log.info("applied migration %s", name)
        newly_applied.append(name)

    if not newly_applied:
        log.info("database is up to date, no migrations to apply")
    return newly_applied
