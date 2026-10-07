#!/bin/sh
set -e
python manage.py migrate --noinput
if [ -f /app/data/migracao_inicial_historico_egidio.json ]; then
  COUNT=$(python manage.py shell -c "from historico.models import Aluno; print(Aluno.objects.count())" | tail -1)
  if [ "$COUNT" = "0" ]; then
    echo "Carregando migração inicial privada..."
    python manage.py carregar_migracao /app/data/migracao_inicial_historico_egidio.json
  fi
fi
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120
