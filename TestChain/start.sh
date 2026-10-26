#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
.venv/bin/python manage.py migrate --noinput
exec .venv/bin/python manage.py runserver "127.0.0.1:${PORT:-8000}"
