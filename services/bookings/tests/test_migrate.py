import pymssql
import pytest

from padel.db import connect
from padel.migrate import MIGRATIONS_DIR, migrate, migration_files
from tests.conftest import get_test_database_url, recreate_database


@pytest.fixture
def empty_conn():
    """A connection to a second, completely empty database.

    The runner is tested with small made-up migrations here, so the real
    test database is not touched.
    """
    url = get_test_database_url() + "_migrate"
    recreate_database(url)
    connection = connect(url)
    yield connection
    connection.close()


def write(folder, name, sql):
    (folder / name).write_text(sql)


def test_migration_files_are_sorted_and_other_files_ignored(tmp_path):
    for name in ["002_b.sql", "001_a.sql", "README.md", "10_bad_name.sql"]:
        write(tmp_path, name, "")

    assert migration_files(tmp_path) == ["001_a.sql", "002_b.sql"]


def test_the_real_migrations_folder_starts_with_001_init():
    assert migration_files(MIGRATIONS_DIR)[0] == "001_init.sql"


def test_migrate_runs_files_in_order_and_records_them(empty_conn, tmp_path):
    write(tmp_path, "001_create.sql", "CREATE TABLE things (id INT PRIMARY KEY, name NVARCHAR(20));")
    write(tmp_path, "002_insert.sql", "INSERT INTO things (id, name) VALUES (1, 'racket');")

    applied = migrate(empty_conn, tmp_path)

    assert applied == ["001_create.sql", "002_insert.sql"]
    versions = empty_conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    assert [row["version"] for row in versions] == ["001_create.sql", "002_insert.sql"]


def test_second_run_applies_nothing(empty_conn, tmp_path):
    write(tmp_path, "001_create.sql", "CREATE TABLE things (id INT PRIMARY KEY);")
    migrate(empty_conn, tmp_path)

    assert migrate(empty_conn, tmp_path) == []


def test_new_migration_keeps_existing_rows(empty_conn, tmp_path):
    write(tmp_path, "001_create.sql", "CREATE TABLE things (id INT PRIMARY KEY);")
    migrate(empty_conn, tmp_path)
    empty_conn.execute("INSERT INTO things (id) VALUES (1), (2)")
    empty_conn.commit()

    write(tmp_path, "002_add_colour.sql",
          "ALTER TABLE things ADD colour NVARCHAR(20) NOT NULL DEFAULT 'blue';")
    assert migrate(empty_conn, tmp_path) == ["002_add_colour.sql"]

    rows = empty_conn.execute("SELECT id, colour FROM things ORDER BY id").fetchall()
    assert rows == [{"id": 1, "colour": "blue"}, {"id": 2, "colour": "blue"}]


def test_failed_migration_changes_nothing_and_is_not_recorded(empty_conn, tmp_path):
    write(tmp_path, "001_broken.sql",
          "CREATE TABLE things (id INT PRIMARY KEY); INSERT INTO no_such_table VALUES (1);")

    with pytest.raises(pymssql.Error):
        migrate(empty_conn, tmp_path)

    tables = empty_conn.execute(
        "SELECT TABLE_NAME AS name FROM INFORMATION_SCHEMA.TABLES"
    ).fetchall()
    assert [row["name"] for row in tables] == ["schema_migrations"]
    assert empty_conn.execute("SELECT COUNT(*) AS n FROM schema_migrations").fetchone()["n"] == 0
