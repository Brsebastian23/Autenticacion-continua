#!/usr/bin/env sh
set -e

# Aplicar migraciones (crea tablas en el esquema ml de Supabase).
python manage.py migrate --noinput

# Seed: entrena SOLO los sujetos cuyos .joblib falten en disco.
# Los 51 modelos del dataset vienen empaquetados en la imagen, así que en un
# deploy normal este paso NO reentrena nada. Solo actúa si faltan archivos.
python - <<'PY'
import os, csv, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "continuous_auth.settings")
django.setup()
from django.conf import settings
from pathlib import Path
from authentication_api.ml_service import model_path_for

ds = Path(settings.DATASET_PATH)
missing = []
if ds.exists():
    subjects = sorted({r["subject"] for r in csv.DictReader(open(ds))})
    missing = [s for s in subjects if not model_path_for(s).exists()]

if missing:
    print(f"Seed: faltan {len(missing)} modelos, entrenando: {missing[:5]}...")
    from django.core.management import call_command
    args = sum([["--subject", s] for s in missing], [])
    call_command("train_from_csv", "--no-eval", *args)
else:
    print("Seed: todos los modelos del dataset ya están presentes. No se entrena.")
PY

# Servidor de producción
exec gunicorn continuous_auth.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout 120
