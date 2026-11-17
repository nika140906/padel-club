# Padel Club

## Overview

A small backend for a padel club of a few hundred members. In Assignment 1 it was one Flask app with one SQLite database. In Assignment 2 it is being split into two services, one per feature domain, each with its own database:

- **bookings** (`services/bookings/`): members register and log in, see the club's four courts, check a court's schedule for a day, book a 60 or 90 minute slot between 08:00 and 23:00, and cancel their own bookings. Double-bookings are rejected.
- **ladder** (`services/ladder/`): members join the ladder under a nickname, record doubles matches they played in, and climb a leaderboard ranked by Elo rating (everyone starts at 1000).

Login lives in the bookings service. It returns a signed token, and the browser sends it to both services in the `Authorization: Bearer <token>` header. Both services check the token with the same `TOKEN_SECRET`, so the ladder knows who is logged in without calling bookings.

One request crosses between the services. When a member joins the ladder, the ladder calls `GET /auth/me` on bookings with the member's own token, to check the account exists and to get the username (used as the nickname if none is given). The ladder finds bookings through `BOOKINGS_URL` and waits at most `BOOKINGS_TIMEOUT_S` seconds. If bookings is down or too slow, joining returns `503` with a message to try again, and everything else in the ladder keeps working. See ADR-6.

```
services/
  bookings/   app.py, padel/auth, padel/bookings, migrations/, tests/, Dockerfile, requirements.txt
  ladder/     app.py, padel/ladder, padel/auth (token check only), migrations/, tests/, Dockerfile, requirements.txt
db/init.sql           creates the two local databases and their logins
docker-compose.yml    the whole system on one machine
```

Each service keeps its data in its own SQL Server database (`bookings` or `ladder`) and logs in with its own user, which cannot open the other database.

## Run with Docker Compose

You need Docker Desktop. On an Apple-chip Mac, SQL Server runs through Rosetta (Settings → General → "Use Rosetta for x86_64/amd64 emulation", on by default).

First make your `.env` file. It holds the passwords and is ignored by Git:

```bash
cp .env.example .env
echo "Pw1-$(openssl rand -hex 16)"    # run three times: one password each for MSSQL_SA, BOOKINGS_DB, LADDER_DB
openssl rand -hex 32                  # for TOKEN_SECRET
```

Paste the values into `.env`, then start everything:

```bash
docker compose up --build
```

This starts SQL Server, runs `db/init.sql` once it is ready (it creates the databases and logins, and is safe to run again), then starts the two services. Each service applies its own migrations when it starts. The bookings service is on `localhost:8001` and the ladder on `localhost:8002`. Check them with `curl localhost:8001/health` and `curl localhost:8002/health`.

`docker compose down` stops everything and keeps the data. `docker compose down -v` also deletes the database volume, so only use it when you want to start from empty.

Never commit a real secret. Real values only live in the local `.env` file (ignored by Git) or in GitHub Actions secrets.

## Run one service without Docker

Requires Python 3.12+ and a running SQL Server (for example `docker compose up -d db db-init`).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r services/bookings/requirements-dev.txt -r services/ladder/requirements-dev.txt
set -a && source .env && set +a      # load the passwords from .env into this terminal

cd services/bookings
DATABASE_URL="mssql://bookings_user:$BOOKINGS_DB_PASSWORD@localhost:1433/bookings" PORT=8001 python app.py
```

## Database migrations

Each service has a `migrations/` folder with numbered SQL files (`001_init.sql`, `002_...`). On start, the service runs the files it has not run before, in order, and records each one in its `schema_migrations` table. A second start applies nothing. Each file runs in one transaction, so a failing migration changes nothing. Applied files are never edited; a fix goes in a new file.

## Configuration

Each service reads:

| Variable       | Default | Purpose |
|----------------|---------|---------|
| `PORT`         | `8000`  | Port the service listens on (binds to 0.0.0.0) |
| `DATABASE_URL` | none, required, secret | The service's own database, as `mssql://user:password@host:1433/database` |
| `TOKEN_SECRET` | none, required, secret | Signs and checks login tokens. Must be the same in both services |
| `CORS_ORIGIN`  | `http://localhost:8080` | The UI's origin, the only website allowed to call the service from a browser |
| `GIT_SHA`      | `dev` | The commit the image was built from, shown by `/health`. Set at build time with `--build-arg GIT_SHA=<sha>` |

The ladder service also reads:

| Variable             | Default | Purpose |
|----------------------|---------|---------|
| `BOOKINGS_URL`       | `http://bookings:8000` | Base URL of the bookings service |
| `BOOKINGS_TIMEOUT_S` | `3` | Seconds to wait for bookings before joining fails with `503` |

A service refuses to start if `DATABASE_URL` or `TOKEN_SECRET` is missing.

## API

All requests and responses are JSON. Every route except `/health`, `/auth/register` and `/auth/login` needs a valid token in the `Authorization: Bearer <token>` header, otherwise it returns `401`. Routes under `/auth`, `/courts` and `/bookings` are on the bookings service; routes under `/ladder` are on the ladder service.

| Method | Path | Body | What it does |
|--------|------|------|--------------|
| GET    | `/health` | | `200 {"status": "ok", "db": "ok", "version": "<git sha>"}` if the service can read and write its own database, otherwise `503` with `"error"` |
| POST   | `/auth/register` | `{"username", "password"}` | Create an account |
| POST   | `/auth/login` | `{"username", "password"}` | Log in, returns `{"id", "username", "token"}` |
| GET    | `/auth/me` | | The logged-in user, or `404` if the account no longer exists. The ladder also calls this |
| GET    | `/courts` | | List courts |
| GET    | `/courts/<id>/bookings?day=YYYY-MM-DD` | | A court's bookings for one day |
| POST   | `/bookings` | `{"court_id", "start_time": "YYYY-MM-DD HH:MM", "duration_minutes": 60 or 90}` | Book a court |
| GET    | `/bookings/mine` | | My bookings |
| DELETE | `/bookings/<id>` | | Cancel my booking |
| POST   | `/ladder/join` | `{"nickname"}` (optional) | Join the ladder. Calls bookings; `503` if bookings does not answer |
| GET    | `/ladder/me` | | My rating and matches played |
| POST   | `/ladder/matches` | `{"team_a": [id, id], "team_b": [id, id], "winner": "A" or "B"}` | Record a match I played in |
| GET    | `/ladder/leaderboard` | | Everyone, ranked by rating |

Errors come back as `{"error": "..."}` with `400` (broken rule), `401` (not logged in or wrong password), `404` (not found), `409` (court already booked) or `503` (joining the ladder while bookings is not answering).

### Example with curl

```bash
curl -X POST localhost:8001/auth/register -H "Content-Type: application/json" \
     -d '{"username": "nika", "password": "secret123"}'
TOKEN=$(curl -s -X POST localhost:8001/auth/login -H "Content-Type: application/json" \
     -d '{"username": "nika", "password": "secret123"}' | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')
curl -X POST localhost:8001/bookings -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"court_id": 1, "start_time": "2030-06-01 18:00", "duration_minutes": 90}'
curl -X POST localhost:8002/ladder/join -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"nickname": "nika"}'
```

There is no logout route. Tokens are not stored on the server, so a client logs out by forgetting its token. Tokens expire after 12 hours.

## Health, logs and partial failure

`GET /health` on each service opens its own database, reads a row and writes one that is rolled back straight away. It answers `200` if that works and `503` if not, within about 5 seconds. It never calls the other service, so the ladder stays healthy while bookings is down.

Each service writes one log line per request to stdout, for example `INFO padel.requests POST /ladder/join 201 50ms`. See them with `docker compose logs -f ladder`.

To see a partial failure, stop one service with `docker compose stop bookings`. The ladder keeps serving the leaderboard, `/ladder/me` and new matches; only `POST /ladder/join` answers `503` with a message to try again. `docker compose start bookings` brings it back.

## Tests & Coverage

The tests run against a real SQL Server. Each run creates its own test database (`bookings_test` or `ladder_test`), wipes it and runs the migrations into it, so never point `TEST_DATABASE_URL` at a database with real data. With the compose SQL Server running (`docker compose up -d db`):

```bash
set -a && source .env && set +a
cd services/bookings && TEST_DATABASE_URL="mssql://sa:$MSSQL_SA_PASSWORD@localhost:1433/bookings_test" pytest --cov=padel --cov=app
cd services/ladder   && TEST_DATABASE_URL="mssql://sa:$MSSQL_SA_PASSWORD@localhost:1433/ladder_test"   pytest --cov=padel --cov=app
```

The ladder's tests replace the bookings service with a small fake HTTP server (`BookingsStub` in `services/ladder/tests/conftest.py`). It can answer normally, answer 404 or 500, answer too slowly, or be switched off, so the tests cover every way the call to bookings can fail.

Latest result: bookings 109 tests, ladder 79 tests, both at 99% coverage (the only line missed in each is the `python app.py` start-up line).
