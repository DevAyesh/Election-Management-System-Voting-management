#!/bin/sh
set -e
python manage.py migrate candidates 0002 --fake 2>/dev/null || true
python manage.py migrate --noinput || python manage.py migrate --fake-initial --noinput || true
if [ "$DEMO_RESET" = "true" ]; then
  echo "DEMO_RESET=true: clearing demo data"
  python manage.py reset_demo --yes
fi
exec "$@"
