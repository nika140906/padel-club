# Tables owned by the ladder domain.
# Padel is played in pairs, so a match has two players per team.
# user ids point at auth's users table but have no FOREIGN KEY,
# so this domain never depends on another domain's tables.
SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    user_id        INTEGER PRIMARY KEY,
    rating         INTEGER NOT NULL DEFAULT 1000,
    matches_played INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS matches (
    id          INTEGER PRIMARY KEY,
    team_a_p1   INTEGER NOT NULL REFERENCES players(user_id),
    team_a_p2   INTEGER NOT NULL REFERENCES players(user_id),
    team_b_p1   INTEGER NOT NULL REFERENCES players(user_id),
    team_b_p2   INTEGER NOT NULL REFERENCES players(user_id),
    winner      TEXT    NOT NULL CHECK (winner IN ('A', 'B')),
    recorded_by INTEGER NOT NULL,
    played_at   TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
