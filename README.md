# Padel Club

## Overview

A small backend for a padel club of a few hundred members. In Assignment 1 it was one Flask app with one SQLite database. In Assignment 2 it is being split into two services, one per feature domain, each with its own database:

- **bookings** (`services/bookings/`): members register and log in, see the club's four courts, check a court's schedule for a day, book a 60 or 90 minute slot between 08:00 and 23:00, and cancel their own bookings. Double-bookings are rejected.
- **ladder** (`services/ladder/`): members join the ladder under a nickname, record doubles matches they played in, and climb a leaderboard ranked by Elo rating (everyone starts at 1000).

Login lives in the bookings service. It returns a signed token, and the browser sends it to both services in the `Authorization: Bearer <token>` header. Both services check the token with the same `TOKEN_SECRET`, so the ladder knows who is logged in without calling bookings.

```
services/
  bookings/   app.py, padel/auth, padel/bookings, tests/, requirements.txt
  ladder/     app.py, padel/ladder, padel/auth (token check only), tests/, requirements.txt
```

## Setup

Requires Python 3.12+. Each service has its own `requirements.txt`.

```bash
git clone https://github.com/nika140906/padel-club.git
cd padel-club
python3 -m venv .venv
source .venv/bin/activate
pip install -r services/bookings/requirements.txt -r services/ladder/requirements.txt
```

## Run

Both services need the same `TOKEN_SECRET`. Make a random one, then start each service in its own terminal with it:

```bash
openssl rand -hex 32                      # copy the output
export TOKEN_SECRET=<paste it here>       # in both terminals

cd services/bookings && PORT=8001 python app.py
cd services/ladder   && PORT=8002 python app.py
```

Never commit a real secret. Real values only live in environment variables, in a local `.env` file (ignored by Git) or in GitHub Actions secrets.

Each service creates its own database on first start. Check they are up with `curl localhost:8001/health` and `curl localhost:8002/health`.

## Configuration

Both services read the same variables:

| Variable       | Default | Purpose |
|----------------|---------|---------|
| `PORT`         | `8000`  | Port the service listens on (binds to 0.0.0.0) |
| `DATA_DIR`     | `data`  | Folder for the service's SQLite file (`bookings.db` or `ladder.db`) |
| `TOKEN_SECRET` | none, required | Signs and checks login tokens. Must be the same in both services. The service refuses to start without it |

## API

All requests and responses are JSON. Every route except `/health`, `/auth/register` and `/auth/login` needs a valid token in the `Authorization: Bearer <token>` header, otherwise it returns `401`. Routes under `/auth`, `/courts` and `/bookings` are on the bookings service; routes under `/ladder` are on the ladder service.

| Method | Path | Body | What it does |
|--------|------|------|--------------|
| GET    | `/health` | | Health check |
| POST   | `/auth/register` | `{"username", "password"}` | Create an account |
| POST   | `/auth/login` | `{"username", "password"}` | Log in, returns `{"id", "username", "token"}` |
| GET    | `/auth/me` | | The logged-in user |
| GET    | `/courts` | | List courts |
| GET    | `/courts/<id>/bookings?day=YYYY-MM-DD` | | A court's bookings for one day |
| POST   | `/bookings` | `{"court_id", "start_time": "YYYY-MM-DD HH:MM", "duration_minutes": 60 or 90}` | Book a court |
| GET    | `/bookings/mine` | | My bookings |
| DELETE | `/bookings/<id>` | | Cancel my booking |
| POST   | `/ladder/join` | `{"nickname"}` | Join the ladder |
| GET    | `/ladder/me` | | My rating and matches played |
| POST   | `/ladder/matches` | `{"team_a": [id, id], "team_b": [id, id], "winner": "A" or "B"}` | Record a match I played in |
| GET    | `/ladder/leaderboard` | | Everyone, ranked by rating |

Errors come back as `{"error": "..."}` with `400` (broken rule), `401` (not logged in or wrong password), `404` (not found) or `409` (court already booked).

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

## Tests & Coverage

Each service is tested on its own, from its own folder:

```bash
cd services/bookings && pytest --cov=padel --cov=app
cd services/ladder   && pytest --cov=padel --cov=app
```

Latest result: bookings 79 tests, ladder 50 tests, both at 99% coverage (the only line missed in each is the `python app.py` start-up line).
