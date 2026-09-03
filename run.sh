#!/usr/bin/env bash
# Open the ship's gallery viewport. Fires up web.py and serves the results grid.
#
#   ./run.sh              # serve on http://127.0.0.1:8000
#   ./run.sh --port 9000  # or wherever you fancy
#
# Any arguments are passed straight through to web.py (--host, --port).
set -euo pipefail

cd "$(dirname "$0")"
exec python3 web.py "$@"
