#!/usr/bin/env bash
set -o errexit

python manage.py migrate --no-input
python manage.py load_initial_data
python manage.py load_ticket_data
python manage.py ensure_protection_data

exec gunicorn kinobase.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
