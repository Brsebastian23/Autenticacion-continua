"""Métricas de evaluación biométrica reutilizables.

Encapsula el cálculo de FAR, FRR, EER y AUC-ROC sobre arrays de scores genuinos
e impostores, de modo que los comandos de gestión y la API expongan exactamente
los mismos números (una única fuente de verdad).

Convención de decisión:
    un registro se considera LEGÍTIMO si ``score >= threshold``.

Notas teóricas:
- **FAR** (False Acceptance Rate): fracción de impostores aceptados.
- **FRR** (False Rejection Rate): fracción de genuinos rechazados.
- **EER** (Equal Error Rate): umbral donde FAR == FRR. Es el indicador de
  exactitud que pide la pregunta de investigación; cuanto más bajo, mejor.
- **AUC-ROC**: probabilidad de que un genuino puntúe por encima de un impostor.
  Es independiente del umbral y mide el poder de separación del modelo.
"""

from __future__ import annotations

import numpy as np


def far_frr_at(genuine_scores, impostor_scores, threshold: float):
    """Devuelve (FAR, FRR) al umbral dado. ``None`` si un lado está vacío."""
    genuine_scores = np.asarray(genuine_scores, dtype=float)
    impostor_scores = np.asarray(impostor_scores, dtype=float)
    far = float(np.mean(impostor_scores >= threshold)) if impostor_scores.size else None
    frr = float(np.mean(genuine_scores < threshold)) if genuine_scores.size else None
    return far, frr


def eer(genuine_scores, impostor_scores):
    """Equal Error Rate barriendo todos los umbrales candidatos.

    Devuelve un dict con ``eer``, ``far_at_eer``, ``frr_at_eer`` y
    ``threshold_at_eer``, o ``None`` si falta alguno de los dos conjuntos.

    Se barre el conjunto de umbrales formado por los propios scores observados
    (el punto óptimo siempre cae en uno de ellos) y se elige el que minimiza la
    diferencia absoluta |FAR - FRR|.
    """
    genuine_scores = np.asarray(genuine_scores, dtype=float)
    impostor_scores = np.asarray(impostor_scores, dtype=float)
    if genuine_scores.size == 0 or impostor_scores.size == 0:
        return None

    thresholds = np.unique(np.concatenate([genuine_scores, impostor_scores]))
    best = None
    for thr in thresholds:
        far = float(np.mean(impostor_scores >= thr))
        frr = float(np.mean(genuine_scores < thr))
        gap = abs(far - frr)
        if best is None or gap < best[0]:
            best = (gap, far, frr, float(thr))

    return {
        'eer': (best[1] + best[2]) / 2.0,
        'far_at_eer': best[1],
        'frr_at_eer': best[2],
        'threshold_at_eer': best[3],
    }


def auc_roc(genuine_scores, impostor_scores):
    """AUC-ROC vía Mann-Whitney U (prob. de que genuino > impostor)."""
    genuine_scores = np.asarray(genuine_scores, dtype=float)
    impostor_scores = np.asarray(impostor_scores, dtype=float)
    if genuine_scores.size == 0 or impostor_scores.size == 0:
        return None

    all_scores = np.concatenate([genuine_scores, impostor_scores])
    order = np.argsort(all_scores, kind='mergesort')
    ranks = np.empty(len(all_scores), dtype=float)
    ranks[order] = np.arange(1, len(all_scores) + 1)
    n_g = genuine_scores.size
    n_i = impostor_scores.size
    genuine_rank_sum = ranks[:n_g].sum()
    return float((genuine_rank_sum - n_g * (n_g + 1) / 2.0) / (n_g * n_i))


def accuracy_at(genuine_scores, impostor_scores, threshold: float):
    """Exactitud global al umbral: genuinos aceptados + impostores rechazados."""
    genuine_scores = np.asarray(genuine_scores, dtype=float)
    impostor_scores = np.asarray(impostor_scores, dtype=float)
    correct = 0
    total = 0
    if genuine_scores.size:
        correct += int(np.sum(genuine_scores >= threshold))
        total += genuine_scores.size
    if impostor_scores.size:
        correct += int(np.sum(impostor_scores < threshold))
        total += impostor_scores.size
    return (correct / total) if total else None


def summarize_benchmark(per_subject_eers):
    """Estadísticas agregadas del EER sobre un conjunto de sujetos.

    ``per_subject_eers`` es una lista (posiblemente con ``None``) de EER por
    sujeto. Devuelve media, mediana, mínimo, máximo, desviación y nº válidos.
    """
    values = [v for v in per_subject_eers if v is not None]
    if not values:
        return {'count': 0, 'mean': None, 'median': None,
                'min': None, 'max': None, 'std': None}
    arr = np.asarray(values, dtype=float)
    return {
        'count': int(arr.size),
        'mean': float(np.mean(arr)),
        'median': float(np.median(arr)),
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'std': float(np.std(arr)),
    }
