#!/bin/bash
# Convenience script to run the FastAPI development server.
# Usage: ./run.sh
#
# This script starts uvicorn with auto-reload enabled on port 8000.
# The APP_DEBUG environment variable controls whether the /docs and /redoc
# endpoints are available.

cd "$(dirname "$0")"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
