#!/bin/sh
cd "$(dirname "$0")"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python gui.py
else
    python3 gui.py
fi
