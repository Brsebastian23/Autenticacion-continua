"""Capa de Machine Learning para **dinámica del cursor** (mouse dynamics).

Módulo **completamente aditivo**: no modifica el esquema de tecleo (31 features
CMU) ni sus modelos. Añade un conjunto paralelo de features de cursor, un
generador de datos **sintéticos** reproducible y un modelo univariado por
usuario, de forma que:

- El flujo actual de tecleo sigue funcionando exactamente igual.
- Cuando haya captura real de cursor, basta con reemplazar el generador
  sintético por ``records`` reales: las funciones ``train_cursor_model`` y
  ``predict_cursor`` ya aceptan cualquier dict de features de cursor.

Diseño de features (12), normalizadas e independientes de la resolución:

- ``M.speed_mean``       velocidad media del puntero (px/ms)
- ``M.speed_std``        desviación de la velocidad
- ``M.speed_max``        velocidad máxima
- ``M.accel_mean``       aceleración media (variación de velocidad)
- ``M.jitter``           variación de dirección (ruido del pulso)
- ``M.curvature_mean``   curvatura media de la trayectoria (giro)
- ``M.straightness``     1.0 = línea recta perfecta; < 1 = trayecto curvo
- ``M.pause_ratio``      fracción de tiempo sin movimiento
- ``M.pause_count``      nº de pausas (> 100 ms sin movimiento)
- ``M.click_rate``       nº de clics por segundo
- ``M.interclick_mean``  tiempo medio entre clics (ms)
- ``M.path_efficiency``  distancia neta / distancia recorrida

Estas features son genéricas: no dependen de una tarea concreta, así sirven
para "tareas de oficina" (mover, seleccionar, clicar) y para sesiones cortas.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from django.conf import settings

logger = logging.getLogger(__name__)

# --- Esquema de features de cursor -----------------------------------------
CURSOR_FEATURE_COLUMNS = (
    'M.speed_mean',
    'M.speed_std',
    'M.speed_max',
    'M.accel_mean',
    'M.jitter',
    'M.curvature_mean',
    'M.straightness',
    'M.pause_ratio',
    'M.pause_count',
    'M.click_rate',
    'M.interclick_mean',
    'M.path_efficiency',
)

NUM_CURSOR_FEATURES = len(CURSOR_FEATURE_COLUMNS)  # 12

IFOREST_PARAMS = {
    'n_estimators': 200,
    'max_samples': 'auto',
    'contamination': 0.1,
    'random_state': 42,
    'n_jobs': -1,
}

MIN_CURSOR_SAMPLES = 3


class CursorServiceError(Exception):
    """Error controlado de la capa de cursor."""


def _safe_filename(user_id: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(user_id))


def cursor_model_path_for(user_id: str) -> Path:
    """Ruta del modelo de cursor: ``cursor_iforest_<user>.joblib``.

    Se usa un prefijo distinto del de tecleo para no colisionar. Los modelos de
    cursor son SIEMPRE de usuario (mutables), por lo que se guardan en el
    directorio persistente ``ML_USER_MODELS_DIR`` (igual a ``ML_MODELS_DIR`` en
    local/tests).
    """
    models_dir = Path(getattr(settings, 'ML_USER_MODELS_DIR', settings.ML_MODELS_DIR))
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir / f'cursor_iforest_{_safe_filename(user_id)}.joblib'


# --- Vectorización ----------------------------------------------------------
def cursor_record_to_vector(record) -> np.ndarray:
    """Convierte un dict (o lista) de features de cursor en vector [1, 12]."""
    if isinstance(record, (list, tuple)):
        if len(record) != NUM_CURSOR_FEATURES:
            raise CursorServiceError(
                f'El record posicional debe tener {NUM_CURSOR_FEATURES} valores, '
                f'recibidos {len(record)}.'
            )
        values = record
    elif isinstance(record, dict):
        missing = [c for c in CURSOR_FEATURE_COLUMNS if c not in record]
        if missing:
            raise CursorServiceError(f'Faltan features de cursor: {missing[:5]}...')
        values = [record[c] for c in CURSOR_FEATURE_COLUMNS]
    else:
        raise CursorServiceError('Cada record de cursor debe ser dict o lista de números.')

    try:
        vector = np.asarray(values, dtype=np.float64).reshape(1, -1)
    except (TypeError, ValueError) as exc:
        raise CursorServiceError('Las features de cursor deben ser numéricas.') from exc

    if not np.all(np.isfinite(vector)):
        raise CursorServiceError('Las features de cursor contienen NaN o infinito.')
    return vector


def cursor_build_matrix(records) -> np.ndarray:
    if not isinstance(records, list):
        raise CursorServiceError("'records' debe ser un array JSON.")
    if len(records) < MIN_CURSOR_SAMPLES:
        raise CursorServiceError(
            f'Se requieren al menos {MIN_CURSOR_SAMPLES} registros de cursor; '
            f'recibidos {len(records)}.'
        )
    return np.vstack([cursor_record_to_vector(r) for r in records])


# --- Generador sintético ----------------------------------------------------
# Perfiles "de personalidad" del cursor. Cada usuario recibe uno estable
# derivado de su id, de modo que la demo es reproducible sin datos reales.
_SYNTHETIC_PROFILES = {
    'precise':  dict(speed=0.55, speed_std=0.12, accel=0.9,  jitter=0.08,
                     curvature=0.12, straightness=0.92, pause_ratio=0.30,
                     pause_count=4, click_rate=0.9, interclick=420,
                     path_efficiency=0.88),
    'fast':     dict(speed=1.30, speed_std=0.32, accel=2.1,  jitter=0.22,
                     curvature=0.28, straightness=0.78, pause_ratio=0.12,
                     pause_count=1, click_rate=1.7, interclick=260,
                     path_efficiency=0.74),
    'erratic':  dict(speed=0.90, speed_std=0.45, accel=2.8,  jitter=0.42,
                     curvature=0.45, straightness=0.62, pause_ratio=0.22,
                     pause_count=3, click_rate=1.2, interclick=350,
                     path_efficiency=0.66),
    'slow':     dict(speed=0.35, speed_std=0.10, accel=0.5,  jitter=0.10,
                     curvature=0.20, straightness=0.85, pause_ratio=0.45,
                     pause_count=6, click_rate=0.6, interclick=650,
                     path_efficiency=0.80),
}

# Mapeo columna de features -> clave del perfil sintético.
_COLUMN_TO_PROFILE_KEY = {
    'M.speed_mean': 'speed',
    'M.speed_std': 'speed_std',
    'M.speed_max': 'speed',          # escala con la velocidad media
    'M.accel_mean': 'accel',
    'M.jitter': 'jitter',
    'M.curvature_mean': 'curvature',
    'M.straightness': 'straightness',
    'M.pause_ratio': 'pause_ratio',
    'M.pause_count': 'pause_count',
    'M.click_rate': 'click_rate',
    'M.interclick_mean': 'interclick',
    'M.path_efficiency': 'path_efficiency',
}

# Columnas enteras (se redondean a entero en el generador sintético).
_COUNT_COLUMNS = {'M.pause_count'}


def synthetic_profile_for(user_id: str) -> str:
    """Asigna un perfil estable a un usuario (hash determinista)."""
    h = 0
    for ch in str(user_id):
        h = (h * 31 + ord(ch)) % 1_000_003
    keys = list(_SYNTHETIC_PROFILES)
    return keys[h % len(keys)]


def generate_synthetic_cursor_records(user_id: str, n: int = 30,
                                      seed: int | None = None) -> list:
    """Genera ``n`` muestras sintéticas de cursor para ``user_id``.

    Deterministas dado ``(user_id, seed)``. Pensado para arrancar la demo antes
    de tener captura real. Las muestras simulam la variabilidad natural de una
    persona repitiendo una tarea (ruido gaussiano alrededor de su perfil).
    """
    profile_name = synthetic_profile_for(user_id)
    profile = _SYNTHETIC_PROFILES[profile_name]
    # Semilla determinista por usuario para reproducibilidad.
    base_seed = seed if seed is not None else (abs(hash(user_id)) % (2**32))
    rng = np.random.default_rng(base_seed)

    records = []
    for _ in range(n):
        rec = {}
        for col in CURSOR_FEATURE_COLUMNS:
            key = _COLUMN_TO_PROFILE_KEY[col]
            mean = profile[key]
            # Ruido proporcional (5-15% según magnitud) para variabilidad realista.
            sigma = abs(mean) * 0.10 + 0.01
            value = float(rng.normal(mean, sigma))
            # Cotas físicas: nada negativo salvo la aceleración (que puede serlo).
            if key != 'accel':
                value = max(0.0, value)
            # Columnas de conteo se redondean a entero.
            if col in _COUNT_COLUMNS:
                value = float(round(value))
            rec[col] = round(value, 6)
        # Coherencia: straightness y path_efficiency en (0, 1].
        rec['M.straightness'] = float(np.clip(rec['M.straightness'], 0.05, 1.0))
        rec['M.path_efficiency'] = float(np.clip(rec['M.path_efficiency'], 0.05, 1.0))
        rec['M.pause_ratio'] = float(np.clip(rec['M.pause_ratio'], 0.0, 1.0))
        records.append(rec)
    return records


# --- Entrenamiento / inferencia --------------------------------------------
def train_cursor_model(user_id: str, records: list) -> dict:
    """Entrena y persiste un IsolationForest de cursor para el usuario."""
    started = time.perf_counter()
    matrix = cursor_build_matrix(records)

    model = IsolationForest(**IFOREST_PARAMS)
    model.fit(matrix)

    path = cursor_model_path_for(user_id)
    tmp_path = path.with_suffix('.joblib.tmp')
    joblib.dump(
        {'model': model, 'features': CURSOR_FEATURE_COLUMNS, 'user_id': user_id,
         'kind': 'cursor'},
        tmp_path,
    )
    os.replace(tmp_path, path)

    latency_ms = (time.perf_counter() - started) * 1000.0
    logger.info('Modelo de cursor entrenado para %s (%d muestras) en %.1f ms',
                user_id, matrix.shape[0], latency_ms)
    return {
        'samples': int(matrix.shape[0]),
        'model_file': path.name,
        'latency_ms': round(latency_ms, 2),
    }


def cursor_model_exists(user_id: str) -> bool:
    return cursor_model_path_for(user_id).exists()


def load_cursor_model(user_id: str):
    path = cursor_model_path_for(user_id)
    if not path.exists():
        raise CursorServiceError(
            f'No existe un modelo de cursor para "{user_id}". '
            f'Invoca primero /api/cursor/retrain/.'
        )
    bundle = joblib.load(path)
    return bundle['model'] if isinstance(bundle, dict) else bundle


def predict_cursor(user_id: str, record) -> dict:
    """Inferencia de cursor: score + decisión con el umbral configurable."""
    started = time.perf_counter()
    model = load_cursor_model(user_id)
    vector = cursor_record_to_vector(record)
    score = float(model.decision_function(vector)[0])
    threshold = float(getattr(settings, 'ML_CURSOR_DECISION_THRESHOLD',
                              settings.ML_DECISION_THRESHOLD))
    is_legitimate = score >= threshold
    return {
        'confidence_score': round(score, 6),
        'is_legitimate': is_legitimate,
        'threshold': threshold,
        'latency_ms': round((time.perf_counter() - started) * 1000.0, 2),
    }
