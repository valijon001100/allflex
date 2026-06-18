#!/usr/bin/env bash
set -o errexit

if command -v apt-get >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq ffmpeg || true
fi

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py load_tv_channels || true
