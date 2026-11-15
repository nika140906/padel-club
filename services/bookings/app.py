import os

from flask import Flask

from padel.auth.routes import bp as auth_bp
from padel.bookings.routes import bp as bookings_bp
from padel.db import close_db, get_db_path, init_db

# All configuration comes from environment variables.
PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", "data")


def create_app(data_dir=None, token_secret=None):
    # Signs the login tokens. It has no default: both services must use the
    # same value, and a random one would make every token invalid in the ladder.
    token_secret = token_secret or os.environ.get("TOKEN_SECRET")
    if not token_secret:
        raise RuntimeError("TOKEN_SECRET must be set (the same value in both services)")

    app = Flask(__name__)
    app.config["TOKEN_SECRET"] = token_secret
    app.config["DB_PATH"] = get_db_path(data_dir or DATA_DIR)
    init_db(app.config["DB_PATH"])

    app.teardown_appcontext(close_db)
    app.register_blueprint(auth_bp)
    app.register_blueprint(bookings_bp)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
