#!/bin/bash
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt --break-system-packages -q 2>/dev/null || python3 -m pip install -r requirements.txt -q
python3 app.py
