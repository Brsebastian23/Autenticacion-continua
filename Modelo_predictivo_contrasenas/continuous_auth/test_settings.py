"""Settings para ejecutar tests de forma aislada.

Fuerza SQLite en memoria para no depender de DATABASE_URL (Supabase/Postgres),
cuyo esquema y credenciales no deben tocarse en las pruebas.

Uso:
    DJANGO_SETTINGS_MODULE=continuous_auth.test_settings python manage.py test
"""

from .settings import *  # noqa: F401,F403

# El cliente de pruebas de Django usa el host "testserver".
ALLOWED_HOSTS = ['*']

# SQLite en memoria: rápido, aislado y sin esquema externo.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Aislar la persistencia de modelos en un directorio temporal para no ensuciar
# el repo cuando un test entrena un modelo de usuario (user-* / cursor).
import tempfile as _tempfile
_TEST_MODELS_DIR = _tempfile.mkdtemp(prefix='ml_test_models_')
ML_MODELS_DIR = _TEST_MODELS_DIR
ML_USER_MODELS_DIR = _TEST_MODELS_DIR

# Acelerar hashing en tests (no afecta a producción).
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Silenciar logging de niveles bajos durante los tests.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
}
