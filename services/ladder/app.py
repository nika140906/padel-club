import logging
import os

from flask import Flask

from padel.db import close_db, connect
from padel.ladder.routes import bp as ladder_bp
from padel.migrate import migrate

# All configuration comes from environment variables.
PORT = int(os.environ.get("PORT", "8000"))

# Log lines go to stdout, where Docker and Azure collect them.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(database_url=None, token_secret=None):
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

    # Bring the database schema up to date before serving any request.
    conn = connect(database_url)
    try:
        migrate(conn)
    finally:
        conn.close()

    app.teardown_appcontext(close_db)
    app.register_blueprint(ladder_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
