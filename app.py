import os
import secrets

from flask import Flask

from padel.auth.routes import bp as auth_bp
from padel.bookings.routes import bp as bookings_bp
from padel.db import close_db, get_db_path, init_db

# All configuration comes from environment variables, with safe defaults.
PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", "data")
# Signs the login cookie. Without it set, a random key is made on every start,
# which logs everyone out when the app restarts.
SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)


def create_app(data_dir=DATA_DIR):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["DB_PATH"] = get_db_path(data_dir)
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
