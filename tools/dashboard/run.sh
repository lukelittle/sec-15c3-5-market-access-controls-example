#!/bin/bash
# SEC 15c3-5 Live Demo Dashboard — setup & run
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

echo "Starting dashboard on http://localhost:8080"
exec .venv/bin/python3 dashboard.py "$@"
