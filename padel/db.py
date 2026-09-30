import os
import sqlite3

from flask import current_app, g

from padel.auth.schema import SCHEMA as AUTH_SCHEMA
from padel.bookings.schema import SCHEMA as BOOKINGS_SCHEMA
from padel.ladder.schema import SCHEMA as LADDER_SCHEMA

DB_FILENAME = "padel.db"


def get_db_path(data_dir):
    return os.path.join(data_dir, DB_FILENAME)


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # rows can be read by column name
    conn.execute("PRAGMA foreign_keys = ON")  # SQLite has them off by default
    return conn


def init_db(db_path):
    """Create the data folder and all tables. Safe to run on every start."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = connect(db_path)
    try:
        for schema in (AUTH_SCHEMA, BOOKINGS_SCHEMA, LADDER_SCHEMA):
            conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def get_db():
    """Return this request's connection, opening it on first use."""
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"])
    return g.db


def close_db(error=None):
    """Close this request's connection. Flask calls this after every request."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()
