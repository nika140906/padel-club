import os

from flask import Flask

from padel.db import get_db_path, init_db

# All configuration comes from environment variables, with safe defaults.
PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", "data")


def create_app(data_dir=DATA_DIR):
    app = Flask(__name__)
    app.config["DB_PATH"] = get_db_path(data_dir)
    init_db(app.config["DB_PATH"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
