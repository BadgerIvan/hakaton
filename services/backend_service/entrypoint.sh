#!/bin/sh
set -eu
if [ "${1:-}" = "uvicorn" ]; then
    python -m app.migrate
fi
exec "$@"
