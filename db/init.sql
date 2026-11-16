-- Local setup of the shared SQL Server container: one database and one
-- login per service. Each login can only use its own database.
--
-- Run by the one-off "db-init" service in docker-compose.yml on every
-- "docker compose up". It is safe to run again: everything is created only
-- if it is missing, and the passwords are set again from .env.
--
-- $(BOOKINGS_DB_PASSWORD) and $(LADDER_DB_PASSWORD) are sqlcmd variables.
-- sqlcmd fills them in from the environment, so no password is in this file.
--
-- The tables are not created here: each service creates its own with its
-- migrations when it starts.

IF DB_ID(N'bookings') IS NULL CREATE DATABASE bookings;
IF DB_ID(N'ladder') IS NULL CREATE DATABASE ladder;
GO

IF SUSER_ID(N'bookings_user') IS NULL
    CREATE LOGIN bookings_user WITH PASSWORD = N'$(BOOKINGS_DB_PASSWORD)';
ELSE
    ALTER LOGIN bookings_user WITH PASSWORD = N'$(BOOKINGS_DB_PASSWORD)';

IF SUSER_ID(N'ladder_user') IS NULL
    CREATE LOGIN ladder_user WITH PASSWORD = N'$(LADDER_DB_PASSWORD)';
ELSE
    ALTER LOGIN ladder_user WITH PASSWORD = N'$(LADDER_DB_PASSWORD)';
GO

-- A login only gets into a database where it has a user. bookings_user has a
-- user in "bookings" only, so it cannot open "ladder", and the other way round.
-- db_owner lets the service run its own migrations (CREATE and ALTER TABLE).
USE bookings;
IF USER_ID(N'bookings_user') IS NULL CREATE USER bookings_user FOR LOGIN bookings_user;
ALTER ROLE db_owner ADD MEMBER bookings_user;
GO

USE ladder;
IF USER_ID(N'ladder_user') IS NULL CREATE USER ladder_user FOR LOGIN ladder_user;
ALTER ROLE db_owner ADD MEMBER ladder_user;
GO
