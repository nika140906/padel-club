import logging
import os

from flask import Flask

from padel.db import STARTUP_RETRY_DELAYS, close_db, connect
from padel.ladder.routes import bp as ladder_bp
from padel.migrate import migrate
from padel.web import setup_cors, setup_health, setup_request_logs

# All configuration comes from environment variables.
PORT = int(os.environ.get("PORT", "8000"))

# Log lines go to stdout, where Docker and Azure collect them.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(database_url=None, token_secret=None, bookings_url=None):
    # Signs the login tokens. It has no default: both services must use the
    # same value, and a random one would make every token invalid in the ladder.
    token_secret = token_secret or os.environ.get("TOKEN_SECRET")
    if not token_secret:
        raise RuntimeError("TOKEN_SECRET must be set (the same value in both services)")
    # Holds this service's database login, so it is a secret with no default.
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set, e.g. mssql://user:password@host:1433/ladder")

    app = Flask(__name__)
    app.config["TOKEN_SECRET"] = token_secret
    app.config["DATABASE_URL"] = database_url
    # Where the bookings service is. The ladder calls it when a member joins.
    app.config["BOOKINGS_URL"] = bookings_url or os.environ.get("BOOKINGS_URL", "http://bookings:8000")
    # Seconds to wait for the bookings service before giving up with a 503.
    app.config["BOOKINGS_TIMEOUT_S"] = float(os.environ.get("BOOKINGS_TIMEOUT_S", "3"))
    # The only origin whose pages may call this service from a browser (the UI).
    app.config["CORS_ORIGIN"] = os.environ.get("CORS_ORIGIN", "http://localhost:8080")
    # The Git commit this image was built from, shown by /health.
    app.config["VERSION"] = os.environ.get("GIT_SHA", "dev")

    # Bring the database schema up to date before serving any request. On Azure the
    # database may be paused and need about a minute to resume, so keep trying.
    conn = connect(database_url, retry_delays=STARTUP_RETRY_DELAYS, login_timeout=15)
    try:
        migrate(conn)
    finally:
        conn.close()

    app.teardown_appcontext(close_db)
    app.register_blueprint(ladder_bp)
    setup_health(app)
    setup_cors(app)
    setup_request_logs(app)

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
