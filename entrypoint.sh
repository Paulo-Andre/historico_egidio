#!/bin/sh
set -e

SECRET_FILE=/app/data/.django_secret_key
if [ -z "$DJANGO_SECRET_KEY" ]; then
  if [ ! -f "$SECRET_FILE" ]; then
    python - <<'PY'
import secrets
from pathlib import Path
path = Path("/app/data/.django_secret_key")
path.write_text(secrets.token_urlsafe(64), encoding="utf-8")
path.chmod(0o600)
PY
  fi
  export DJANGO_SECRET_KEY="$(cat "$SECRET_FILE")"
fi

python manage.py migrate --noinput

if [ -f /app/data/migracao_inicial_historico_egidio.json ]; then
  COUNT=$(python manage.py shell -c "from historico.models import Aluno; print(Aluno.objects.count())" | tail -1)
  if [ "$COUNT" = "0" ]; then
    echo "Carregando migração inicial privada..."
    python manage.py carregar_migracao /app/data/migracao_inicial_historico_egidio.json
  fi
fi

exec gunicorn config.wsgi:application   --bind 0.0.0.0:8000   --workers 2   --timeout 180   --access-logfile -   --error-logfile -
