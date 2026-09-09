#!/usr/bin/env bash
set -e

# Run Obol Gateway Service
# User Rule 7: Always bind to 0.0.0.0, not localhost
PORT="${PORT:-8085}"
HOST="${HOST:-0.0.0.0}"

echo "Starting Obol AHP Economic Gateway on ${HOST}:${PORT}..."
exec uvicorn app.main:app --host "${HOST}" --port "${PORT}" --reload
