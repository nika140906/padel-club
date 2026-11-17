"""Request logs, CORS and the health check. This file is the same in both services."""
import logging
import time

from flask import current_app, g, request

from padel.db import connect

log = logging.getLogger("padel.requests")

# The health check gives up on the database after this many seconds,
# so a stuck database makes /health answer 503 instead of hanging.
HEALTH_DB_TIMEOUT_S = 5


def setup_request_logs(app):
    """Write one line per request to stdout: method, path, status and duration."""

    @app.before_request
    def start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def log_request(response):
        started = g.get("request_started", time.perf_counter())
        duration_ms = (time.perf_counter() - started) * 1000
        log.info("%s %s %s %.0fms", request.method, request.path, response.status_code, duration_ms)
        return response


def setup_cors(app):
    """Let the browser call this service from the UI's origin, and only from there.

    A browser only lets a page read a response from another origin if the
    response says that origin is allowed. Before a request with a token or a
    JSON body, the browser first sends an OPTIONS request (the "preflight").
    Flask answers OPTIONS by itself, and this hook adds the headers to it.
    Login is not checked on OPTIONS, because the browser never sends the token there.
    """

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin and origin == current_app.config["CORS_ORIGIN"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Max-Age"] = "600"  # browser may reuse the preflight for 10 minutes
        # The answer depends on the Origin header, so caches must not mix them up.
        response.vary.add("Origin")
        return response


def database_is_ok(database_url):
    """True if this service can read from and write to its own database.

    The write is a row in schema_migrations that is rolled back straight
    away, so nothing is ever kept.
    """
    conn = None
    try:
        conn = connect(database_url, login_timeout=HEALTH_DB_TIMEOUT_S, timeout=HEALTH_DB_TIMEOUT_S)
        conn.execute("SELECT COUNT(*) AS applied FROM schema_migrations").fetchone()
        conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", ("health-check",))
        conn.rollback()
        return True
    except Exception as error:  # any failure means "not healthy", never a crash
        log.warning("health check: database is not ok: %s", error)
        return False
    finally:
        if conn is not None:
            conn.close()


def setup_health(app):
    @app.get("/health")
    def health():
        """200 if this service's own database works, 503 if not.

        It does not check the other service: this service is healthy even
        when the other one is down.
        """
        ok = database_is_ok(current_app.config["DATABASE_URL"])
        state = "ok" if ok else "error"
        body = {"status": state, "db": state, "version": current_app.config["VERSION"]}
        return body, 200 if ok else 503
