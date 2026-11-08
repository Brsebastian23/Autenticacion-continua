"""Capa de servicio de Machine Learning.

Encapsula:
- Las 31 columnas de características del dataset CMU DSL-StrongPasswordData.
- El entrenamiento / carga / inferencia con IsolationForest (scikit-learn).
"""

import os
import re
import time
import logging
from pathlib import Path

from django.conf import settings

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

# Columnas del dataset CMU: 11 H.* (hold time), 10 DD.* (down-down) y 10 UD.* (up-down).
# Se construyen como prefijo + "." + tecla, p. ej. "H.period" o "DD..t.i".
_HOLD_KEYS = ('period', 't', 'i', 'e', 'five', 'Shift.r', 'o', 'a', 'n', 'l', 'Return')
_FLIGHT_KEYS = ('.period.t', '.t.i', '.i.e', '.e.five', '.five.Shift.r',
                '.Shift.r.o', '.o.a', '.a.n', '.n.l', '.l.Return')

FEATURE_COLUMNS = (
    [f'H.{key}' for key in _HOLD_KEYS]
    + [f'DD{key}' for key in _FLIGHT_KEYS]
    + [f'UD{key}' for key in _FLIGHT_KEYS]
)

NUM_FEATURES = len(FEATURE_COLUMNS)  # 31

# Hiper-parámetros del modelo
IFOREST_PARAMS = {
    'n_estimators': 200,
    'max_samples': 'auto',
    'contamination': 0.1,
    'random_state': 42,
    'n_jobs': -1,
}

MIN_TRAINING_SAMPLES = 3


class MLServiceError(Exception):
    """Error controlado de la capa ML."""


def _safe_filename(user_id: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(user_id))


def is_user_model(user_id: str) -> bool:
    """¿El id corresponde a un modelo PROPIO de usuario?

    Los modelos del dataset CMU se identifican como ``s002`` (sujeto + número).
    Los modelos entrenados por usuarios reales los crea el backend como
    ``user-<username>``. Solo los de usuario son mutables y, por tanto, deben
    persistirse en el volumen.
    """
    return str(user_id).startswith('user-')


def _models_dir_for(user_id: str) -> Path:
    """Devuelve el directorio donde debe vivir el modelo de ``user_id``.

    - Modelos de usuario (``user-*``) -> ``ML_USER_MODELS_DIR`` (persistente).
    - Modelos del dataset (``sXXX``)  -> ``ML_MODELS_DIR`` (en la imagen).

    Si no existe ``ML_USER_MODELS_DIR`` en settings (p. ej. tests antiguos),
    se cae a ``ML_MODELS_DIR`` para no romper compatibilidad.
    """
    if is_user_model(user_id):
        models_dir = Path(getattr(settings, 'ML_USER_MODELS_DIR', settings.ML_MODELS_DIR))
    else:
        models_dir = Path(settings.ML_MODELS_DIR)
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def model_path_for(user_id: str) -> Path:
    return _models_dir_for(user_id) / f'iforest_{_safe_filename(user_id)}.joblib'


def record_to_vector(record: dict) -> np.ndarray:
    """Convierte un dict de métricas (o una lista posicional) en vector float64 [1, 31]."""
    if isinstance(record, (list, tuple)):
        if len(record) != NUM_FEATURES:
            raise MLServiceError(
                f'El record posicional debe tener {NUM_FEATURES} valores, recibidos {len(record)}.'
            )
        values = record
    elif isinstance(record, dict):
        missing = [col for col in FEATURE_COLUMNS if col not in record]
        if missing:
            raise MLServiceError(f'Faltan características en el record: {missing[:5]}...')
        values = [record[col] for col in FEATURE_COLUMNS]
    else:
        raise MLServiceError('Cada record debe ser un objeto JSON o una lista de 31 números.')

    try:
        vector = np.asarray(values, dtype=np.float64).reshape(1, -1)
    except (TypeError, ValueError) as exc:
        raise MLServiceError('Todas las métricas deben ser numéricas.') from exc

    if not np.all(np.isfinite(vector)):
        raise MLServiceError('Las métricas contienen NaN o valores infinitos.')

    return vector


def build_matrix(records: list) -> np.ndarray:
    if not isinstance(records, list):
        raise MLServiceError("'records' debe ser un array JSON.")
    if len(records) < MIN_TRAINING_SAMPLES:
        raise MLServiceError(
            f'Se requieren al menos {MIN_TRAINING_SAMPLES} registros para entrenar; '
            f'recibidos {len(records)}.'
        )
    return np.vstack([record_to_vector(record) for record in records])


def train_model(user_id: str, records: list) -> dict:
    """Entrena y persiste un IsolationForest para el usuario."""
    started = time.perf_counter()
    matrix = build_matrix(records)

    model = IsolationForest(**IFOREST_PARAMS)
    model.fit(matrix)

    path = model_path_for(user_id)
    tmp_path = path.with_suffix('.joblib.tmp')
    joblib.dump(
        {'model': model, 'features': FEATURE_COLUMNS, 'user_id': user_id},
        tmp_path,
    )
    os.replace(tmp_path, path)

    latency_ms = (time.perf_counter() - started) * 1000.0
    logger.info('Modelo entrenado para %s (%d muestras) en %.1f ms',
                user_id, matrix.shape[0], latency_ms)

    return {
        'samples': int(matrix.shape[0]),
        'model_file': path.name,
        'latency_ms': round(latency_ms, 2),
    }


def model_exists(user_id: str) -> bool:
    return model_path_for(user_id).exists()


def load_model(user_id: str):
    path = model_path_for(user_id)
    if not path.exists():
        raise MLServiceError(
            f'No existe un modelo entrenado para el usuario "{user_id}". '
            f'Invoca primero /api/retrain/.'
        )
    bundle = joblib.load(path)
    if isinstance(bundle, dict):
        return bundle['model']
    return bundle


def evaluate_model(model, genuine_records: list, impostor_records: list,
                   threshold: float = 0.0) -> dict:
    """Evalúa un modelo ya entrenado con datos NO vistos.

    - genuine_records: registros del usuario legítimo (sesiones de test).
    - impostor_records: registros de otros sujetos (impostores).

    Devuelve FAR (impostores aceptados), FRR (legítimos rechazados) y exactitud.
    Un registro se considera legítimo si decision_function >= threshold.
    """
    def _scores(records):
        if not records:
            return np.empty((0,))
        matrix = np.vstack([record_to_vector(r) for r in records])
        return model.decision_function(matrix)

    genuine_scores = _scores(genuine_records)
    impostor_scores = _scores(impostor_records)

    # FAR: fracción de impostores aceptados (score >= threshold).
    far = float(np.mean(impostor_scores >= threshold)) if impostor_scores.size else None
    # FRR: fracción de legítimos rechazados (score < threshold).
    frr = float(np.mean(genuine_scores < threshold)) if genuine_scores.size else None

    correct = 0
    total = 0
    if genuine_scores.size:
        correct += int(np.sum(genuine_scores >= threshold))
        total += genuine_scores.size
    if impostor_scores.size:
        correct += int(np.sum(impostor_scores < threshold))
        total += impostor_scores.size

    return {
        'far': far,
        'frr': frr,
        'accuracy': (correct / total) if total else None,
        'n_genuine': int(genuine_scores.size),
        'n_impostor': int(impostor_scores.size),
    }


def predict(user_id: str, record) -> dict:
    """Ejecuta la inferencia y devuelve score + decisión."""
    started = time.perf_counter()
    model = load_model(user_id)
    vector = record_to_vector(record)

    # decision_function: < 0 => anomalía (impostor), >= 0 => normal (legítimo)
    score = float(model.decision_function(vector)[0])
    is_legitimate = score >= float(settings.ML_DECISION_THRESHOLD)

    return {
        'confidence_score': round(score, 6),
        'is_legitimate': is_legitimate,
        'latency_ms': round((time.perf_counter() - started) * 1000.0, 2),
    }
