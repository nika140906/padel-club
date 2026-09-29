# Padel Club

## Overview

TODO: Describe the app and its two feature domains (Court Bookings and Match Ladder).

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

The app starts on `http://0.0.0.0:8000`. Check it is up with `curl http://localhost:8000/health`, which returns `{"status": "ok"}`.

## Configuration

All configuration is done with environment variables. None are required.

| Variable   | Default | Purpose                                     |
|------------|---------|---------------------------------------------|
| `PORT`     | `8000`  | Port the app listens on (binds to 0.0.0.0)  |
| `DATA_DIR` | `data`  | Folder for the SQLite database, stored at `DATA_DIR/padel.db` and created automatically on start |

Example: `PORT=9000 DATA_DIR=/tmp/padel python app.py`

## Tests & Coverage

```bash
pytest --cov=padel --cov=app
```

TODO: Latest coverage result.
