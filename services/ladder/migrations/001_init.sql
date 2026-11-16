-- Tables of the ladder service: players and matches.
-- Ported from the SQLite schema of Assignment 1.
--
-- Padel is played in pairs, so a match has two players per team.
-- players.user_id is the id of the member in the bookings service. It is a
-- plain number here: the users table lives in the other service's database,
-- so there can be no FOREIGN KEY to it.
-- Players choose a nickname when they join, so the leaderboard can show
-- names without asking the bookings service.
--
-- Nicknames are compared case-sensitively, the same as in SQLite
-- (CS = case-sensitive; SQL Server's default is case-insensitive).

CREATE TABLE players (
    user_id        INT          NOT NULL PRIMARY KEY,
    nickname       NVARCHAR(20) COLLATE Latin1_General_100_CS_AS NOT NULL UNIQUE,
    rating         INT          NOT NULL DEFAULT 1000,
    matches_played INT          NOT NULL DEFAULT 0
);

CREATE TABLE matches (
    id          INT IDENTITY(1, 1) PRIMARY KEY,
    team_a_p1   INT          NOT NULL REFERENCES players (user_id),
    team_a_p2   INT          NOT NULL REFERENCES players (user_id),
    team_b_p1   INT          NOT NULL REFERENCES players (user_id),
    team_b_p2   INT          NOT NULL REFERENCES players (user_id),
    winner      NCHAR(1)     NOT NULL CONSTRAINT matches_winner_a_or_b CHECK (winner IN ('A', 'B')),
    recorded_by INT          NOT NULL,
    played_at   DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME()
);
