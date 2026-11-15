# Tables owned by the bookings domain.
# bookings.user_id points at auth's users table but has no FOREIGN KEY,
# so this domain never depends on another domain's tables.
# Times are stored as ISO text ("2026-10-01 18:00"), which sorts correctly.
SCHEMA = """
CREATE TABLE IF NOT EXISTS courts (
    id   INTEGER PRIMARY KEY,
    name TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS bookings (
    id         INTEGER PRIMARY KEY,
    court_id   INTEGER NOT NULL REFERENCES courts(id),
    user_id    INTEGER NOT NULL,
    start_time TEXT    NOT NULL,
    end_time   TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_time > start_time)
);

INSERT OR IGNORE INTO courts (name) VALUES
    ('Court 1'), ('Court 2'), ('Court 3'), ('Court 4');
"""
