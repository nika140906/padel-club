# Image for the bookings service (login, courts and bookings).
# Exact Python version, so every build starts from the same base.
FROM python:3.12.13-slim-bookworm

# Do not write .pyc files; send print/log output straight to stdout.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first: Docker reuses this layer until requirements.txt changes.
# requirements.txt pins every package to an exact version.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then only the code the service needs. No tests, no .env, no secrets:
# configuration arrives as environment variables when the container starts.
COPY app.py .
COPY padel/ padel/
COPY migrations/ migrations/

# Run as an ordinary user, not root.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

ENV PORT=8000
EXPOSE 8000

# gunicorn is a production web server. One worker process, so the migrations
# in create_app() run once per container; four threads serve requests side by side.
# --no-control-socket: we never send commands to a running gunicorn, so it needs no socket.
# "exec" makes gunicorn the main process, so it receives Docker's stop signal.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --no-control-socket 'app:create_app()'"]
