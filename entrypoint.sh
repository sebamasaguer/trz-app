#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
