#!/usr/bin/env bash
set -o errexit

python manage.py migrate --no-input
python manage.py load_initial_data

exec gunicorn kinobase.wsgi:application --bind "0.0.0.0:${PORT:-8000}"
