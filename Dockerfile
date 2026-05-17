# syntax=docker/dockerfile:1
#
# Minimal container image for the prototype API.
#
# The image is intentionally small and dependency-free: the prototype runs
# entirely on the Python standard library, so we only need a base interpreter
# and the application source.
#
# Build:
#   docker build -t internet-voting-system-api .
# Run (memory storage):
#   docker run --rm -p 8787:8787 internet-voting-system-api
# Run (SQLite storage, with persistent volume):
#   docker run --rm -p 8787:8787 -v vote-data:/data \
#     internet-voting-system-api \
#     --storage sqlite --sqlite-path /data/voting.sqlite3

FROM python:3.12-slim AS base

# Run as a non-root user; the prototype never needs root privileges.
RUN useradd --create-home --uid 1000 voting

WORKDIR /app

# Copy the API source. The prototype has no third-party dependencies, so we
# skip pip-install entirely. Replace this with `pip install -r requirements.txt`
# once FastAPI / psycopg / crypto libraries are introduced.
COPY services/api/internet_voting_system /app/internet_voting_system

# /data is the recommended SQLite volume mount point.
RUN mkdir -p /data && chown -R voting:voting /app /data
USER voting

EXPOSE 8787

# Default to in-memory storage so the image works without any volume.
# Override by passing `--storage sqlite --sqlite-path /data/voting.sqlite3`.
ENTRYPOINT ["python", "-m", "internet_voting_system.app", "--host", "0.0.0.0", "--port", "8787"]
CMD ["--storage", "memory"]
