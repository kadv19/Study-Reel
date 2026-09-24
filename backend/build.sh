#!/usr/bin/env bash
set -e
pip install -r requirements.txt
python -c "import httpx; print('httpx ok')"
