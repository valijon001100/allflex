#!/usr/bin/env bash
set -o errexit

echo "Running migrations..."
if ! python manage.py migrate --no-input; then
    echo "Migrate failed, retrying in 5s..."
    sleep 5
    python manage.py migrate --no-input
fi

# Telekanallar bo'limidagi kinolarni tuzatish (har deployda xavfsiz).
python manage.py fix_movie_categories || true
python manage.py seed_film_subcategories || true
python manage.py seed_genres || true

# Bo'sh bo'lsa namuna bilet tadbirlari (mavjud ma'lumotga tegmaydi).
python manage.py load_ticket_data || true

# Ma'lumotlar bazasini deployda o'zgartirmaymiz (faqat schema migrate).
# Birinchi marta to'liq seed kerak bo'lsa: RUN_DEPLOY_SEED=true qo'ying.
if [ "${RUN_DEPLOY_SEED:-false}" = "true" ]; then
    python manage.py load_initial_data || true
    python manage.py load_tv_channels --priority || true
    python manage.py load_tv_channels --all-countries --min-countries 50 || true
    python manage.py refresh_channel_logos || true
fi

if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_WEBHOOK_URL:-}" ]; then
    python manage.py setup_telegram_webhook || true
fi

echo "Starting gunicorn..."
exec gunicorn kinobase.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --timeout 120 \
    --preload
