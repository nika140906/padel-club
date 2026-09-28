import os

from flask import Flask

# All configuration comes from environment variables, with safe defaults.
PORT = int(os.environ.get("PORT", "8000"))
DATA_DIR = os.environ.get("DATA_DIR", "data")


def create_app():
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    create_app().run(host="0.0.0.0", port=PORT)
