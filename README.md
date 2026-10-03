# Padel Club

## Overview

A small backend for a padel club of a few hundred members. It is a JSON API built with Flask and SQLite, running as a single process.

Members register and log in, then use two separate features:

- **Court Bookings**: see the club's four courts, check a court's schedule for a day, book a 60 or 90 minute slot between 08:00 and 23:00, and cancel their own bookings. Double-bookings are rejected.
- **Match Ladder**: join the ladder under a nickname, record doubles matches they played in, and climb a leaderboard ranked by Elo rating (everyone starts at 1000).

The code is split into three modules under `padel/`: `auth`, `bookings` and `ladder`. Each owns its own tables and logic, and bookings and ladder never use each other's code (see `ADR.md`).

## Setup

Requires Python 3.12+.

```bash
git clone https://github.com/nika140906/padel-club.git
cd padel-club
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

The app starts on `http://0.0.0.0:8000` and creates its database on first start, so no other setup is needed. Check it is up with `curl http://localhost:8000/health`, which returns `{"status": "ok"}`.

## Configuration

All configuration is done with environment variables. None are required.

| Variable     | Default              | Purpose                                                                 |
|--------------|----------------------|-------------------------------------------------------------------------|
| `PORT`       | `8000`               | Port the app listens on (binds to 0.0.0.0)                              |
| `DATA_DIR`   | `data`               | Folder for the SQLite database, stored at `DATA_DIR/padel.db` and created automatically on start |
| `SECRET_KEY` | random on each start | Signs the login cookie. Set it so logins survive a restart              |

Example: `PORT=9000 DATA_DIR=/tmp/padel SECRET_KEY=change-me python app.py`

## API

All requests and responses are JSON. Every route except `/health`, `/auth/register` and `/auth/login` needs a logged-in user, otherwise it returns `401`.

| Method | Path | Body | What it does |
|--------|------|------|--------------|
| GET    | `/health` | | Health check |
| POST   | `/auth/register` | `{"username", "password"}` | Create an account |
| POST   | `/auth/login` | `{"username", "password"}` | Log in (sets a session cookie) |
| POST   | `/auth/logout` | | Log out |
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
curl -X POST localhost:8000/auth/register -H "Content-Type: application/json" \
     -d '{"username": "nika", "password": "secret123"}'
curl -c /tmp/padel-cookies.txt -X POST localhost:8000/auth/login -H "Content-Type: application/json" \
     -d '{"username": "nika", "password": "secret123"}'
curl -b /tmp/padel-cookies.txt -X POST localhost:8000/bookings -H "Content-Type: application/json" \
     -d '{"court_id": 1, "start_time": "2026-10-10 18:00", "duration_minutes": 90}'
```

`-c` saves the login cookie and `-b` sends it back on later requests.

## Tests & Coverage

```bash
pytest --cov=padel --cov=app
```

Latest result: 110 tests passed, 99% coverage (321 statements, 1 missed: the `python app.py` start-up line, which tests never run).
