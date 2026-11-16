-- Tables of the bookings service: users (auth) and courts + bookings.
-- Ported from the SQLite schema of Assignment 1.
--
-- bookings.user_id points at users.id but has no FOREIGN KEY, as before,
-- so the bookings domain does not depend on the auth domain's tables.
--
-- Usernames are compared case-sensitively ("Nika" and "nika" are two
-- different users), the same as in SQLite. SQL Server's default is
-- case-insensitive, so the column sets its own collation (CS = case-sensitive).

CREATE TABLE users (
    id            INT IDENTITY(1, 1) PRIMARY KEY,
    username      NVARCHAR(30) COLLATE Latin1_General_100_CS_AS NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    created_at    DATETIME2(0)  NOT NULL DEFAULT SYSUTCDATETIME()
);

CREATE TABLE courts (
    id   INT IDENTITY(1, 1) PRIMARY KEY,
    name NVARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE bookings (
    id         INT IDENTITY(1, 1) PRIMARY KEY,
    court_id   INT          NOT NULL REFERENCES courts (id),
    user_id    INT          NOT NULL,
    start_time DATETIME2(0) NOT NULL,
    end_time   DATETIME2(0) NOT NULL,
    created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT bookings_end_after_start CHECK (end_time > start_time)
);

-- The club's four courts. This file runs only once, so they are never duplicated.
INSERT INTO courts (name) VALUES ('Court 1'), ('Court 2'), ('Court 3'), ('Court 4');
