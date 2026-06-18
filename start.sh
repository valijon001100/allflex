#!/usr/bin/env bash
set -o errexit

echo "Running migrations..."
if ! python manage.py migrate --no-input; then
    echo "Migrate failed, retrying in 5s..."
    sleep 5
    python manage.py migrate --no-input
fi

python manage.py load_initial_data || true
python manage.py load_ticket_data || true
python manage.py ensure_protection_data || true
python manage.py load_tv_channels --all-countries || true
python manage.py refresh_channel_logos || true

echo "Starting gunicorn..."
exec gunicorn kinobase.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --timeout 120 \
    --preload
