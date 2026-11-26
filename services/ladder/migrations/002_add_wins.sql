-- Count each player's wins, so the leaderboard can show them next to
-- matches played.
--
-- The players table already holds data on Azure, so the column is added in
-- place, never by recreating the table. Existing rows get 0 first, then the
-- real number is filled in from the matches table: a player won a match if
-- they were on the team named in matches.winner.
--
-- SQL Server checks every column name in a file before it runs any of it,
-- and at that moment players.wins does not exist yet. So the UPDATE goes in
-- EXEC(...), which is checked only when it runs, after the ALTER TABLE.
-- Both still run in the runner's one transaction for this file.

ALTER TABLE players
    ADD wins INT NOT NULL CONSTRAINT players_wins_default DEFAULT 0;

EXEC(N'
UPDATE players
SET wins = (
    SELECT COUNT(*)
    FROM matches
    WHERE (matches.winner = ''A'' AND players.user_id IN (matches.team_a_p1, matches.team_a_p2))
       OR (matches.winner = ''B'' AND players.user_id IN (matches.team_b_p1, matches.team_b_p2))
);
');
