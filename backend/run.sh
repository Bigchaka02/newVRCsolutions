#!/usr/bin/env bash
# Development server. For production use gunicorn with uvicorn workers behind
# nginx or Cloudflare — see README.
set -euo pipefail

if [ ! -d .venv ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip
  ./.venv/bin/pip install -r requirements.txt
fi

[ -f .env ] || cp .env.example .env

./.venv/bin/python -m app.seed
exec ./.venv/bin/uvicorn app.main:app --reload --port 8000
