"""Evalúa los modelos entrenados comparando rendimiento en datos VISTOS
(entrenamiento) vs datos NO VISTOS (test), para detectar overfitting.

Usa el mismo split por sesión que train_from_csv.py:
- Entrenamiento: sesiones en --train-sessions (por defecto 1..6).
- Test: el resto de sesiones del usuario (por defecto 7 y 8).
Los impostores son los otros sujetos en las mismas sesiones.

Métricas por sujeto y agregadas: FAR, FRR, accuracy, EER, AUC y separación
de scores (media genuina vs media impostora).

Uso:
    python manage.py evaluate_models
    python manage.py evaluate_models --subject s002
    python manage.py evaluate_models --train-sessions 1-7
"""

from pathlib import Path

import numpy as np

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from authentication_api.ml_service import (
    FEATURE_COLUMNS,
    MLServiceError,
    load_model,
    record_to_vector,
)
from authentication_api.models import UserProfile

DEFAULT_TRAIN_SESSIONS = '1-6'


def _parse_sessions(value):
    sessions = set()
    for part in str(value).split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-', 1)
            sessions.update(range(int(start), int(end) + 1))
        else:
            sessions.add(int(part))
    return sessions


def _eer(genuine_scores, impostor_scores):
    """Equal Error Rate: punto donde FAR == FRR, barriendo umbrales."""
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
    return {'eer': (best[1] + best[2]) / 2.0, 'far_at_eer': best[1],
            'frr_at_eer': best[2], 'threshold_at_eer': best[3]}


def _auc(genuine_scores, impostor_scores):
    """AUC-ROC vía Mann-Whitney U (prob. de que genuino > impostor)."""
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


class Command(BaseCommand):
    help = 'Evalúa modelos entrenados en datos vistos (train) vs no vistos (test).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dataset',
            default=str(Path(settings.DATASET_PATH)),
            help='Ruta del CSV (por defecto: settings.DATASET_PATH).',
        )
        parser.add_argument(
            '--subject',
            action='append',
            default=None,
            help='Sujeto a evaluar (p. ej. s002). Se puede repetir.',
        )
        parser.add_argument(
            '--train-sessions',
            default=DEFAULT_TRAIN_SESSIONS,
            help=f'Sesiones usadas para entrenar (por defecto: {DEFAULT_TRAIN_SESSIONS}).',
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=float(settings.ML_DECISION_THRESHOLD),
            help='Umbral para FAR/FRR/accuracy (por defecto: ML_DECISION_THRESHOLD).',
        )
        parser.add_argument(
            '--per-subject',
            action='store_true',
            help='Mostrar una línea de métricas por cada sujeto.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Máximo de sujetos a evaluar.',
        )

    def handle(self, *args, **options):
        import csv
        from collections import defaultdict

        dataset_path = Path(options['dataset'])
        if not dataset_path.exists():
            raise CommandError(f'No se encontró el dataset en {dataset_path}')

        train_sessions = _parse_sessions(options['train_sessions'])
        threshold = options['threshold']

        records_by_subject = defaultdict(lambda: defaultdict(list))
        with dataset_path.open(newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            missing = [c for c in FEATURE_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(f'Faltan columnas en el CSV: {missing}')
            # Se carga TODO el dataset: los sujetos filtrados se usan como usuarios
            # a evaluar, y el resto como impostores. Así incluso evaluando un único
            # sujeto hay impostores reales para FAR/AUC.
            for row in reader:
                subject = row['subject']
                try:
                    rec = {c: float(row[c]) for c in FEATURE_COLUMNS}
                except (TypeError, ValueError):
                    continue
                records_by_subject[subject][int(row['sessionIndex'])].append(rec)

        if not records_by_subject:
            raise CommandError('No se encontraron registros.')

        all_subjects = sorted(records_by_subject)
        if options['subject']:
            wanted = set(options['subject'])
            subjects = [s for s in all_subjects if s in wanted]
        else:
            subjects = all_subjects
        if options['limit']:
            subjects = subjects[:options['limit']]

        # Impostores: registros de test de TODOS los demás sujetos del dataset
        # (no vistos por el modelo), aunque se evalúe un único sujeto.
        def _test_records_of(other):
            return [
                r for sess, recs in records_by_subject[other].items()
                if sess not in train_sessions for r in recs
            ]

        rows = []
        for subject in subjects:
            by_session = records_by_subject[subject]
            train_recs = [r for s, recs in by_session.items() if s in train_sessions for r in recs]
            test_recs = [r for s, recs in by_session.items() if s not in train_sessions for r in recs]
            if not train_recs or not test_recs:
                self.stderr.write(f'[{subject}] sin datos de train o test, se omite.')
                continue
            try:
                model = load_model(subject)
            except MLServiceError as exc:
                self.stderr.write(f'[{subject}] {exc}')
                continue

            # Scores sobre datos vistos (train).
            train_matrix = np.vstack([record_to_vector(r) for r in train_recs])
            train_scores = model.decision_function(train_matrix)
            # Scores sobre datos no vistos (test).
            test_matrix = np.vstack([record_to_vector(r) for r in test_recs])
            test_scores = model.decision_function(test_matrix)

            # Impostores de test excluyendo el propio sujeto.
            other_recs = [r for o in all_subjects if o != subject for r in _test_records_of(o)]
            other_matrix = np.vstack([record_to_vector(r) for r in other_recs]) \
                if other_recs else None

            if other_matrix is not None and other_matrix.size:
                imp_scores = model.decision_function(other_matrix)
            else:
                imp_scores = np.empty((0,))

            def _metrics(gen_scores, imp_scores):
                far = float(np.mean(imp_scores >= threshold)) if imp_scores.size else None
                frr = float(np.mean(gen_scores < threshold)) if gen_scores.size else None
                correct = int(np.sum(gen_scores >= threshold)) if gen_scores.size else 0
                total = gen_scores.size
                if imp_scores.size:
                    correct += int(np.sum(imp_scores < threshold))
                    total += imp_scores.size
                acc = correct / total if total else None
                return far, frr, acc

            tr_far, tr_frr, tr_acc = _metrics(train_scores, imp_scores)
            te_far, te_frr, te_acc = _metrics(test_scores, imp_scores)

            rows.append({
                'subject': subject,
                'train_far': tr_far, 'train_frr': tr_frr, 'train_acc': tr_acc,
                'test_far': te_far, 'test_frr': te_frr, 'test_acc': te_acc,
                'train_score_mean': float(np.mean(train_scores)),
                'test_score_mean': float(np.mean(test_scores)),
                'imp_score_mean': float(np.mean(imp_scores)) if imp_scores.size else None,
                'train_accept': float(np.mean(train_scores >= threshold)),
                'test_accept': float(np.mean(test_scores >= threshold)),
                'eer': _eer(test_scores, imp_scores),
                'auc': _auc(test_scores, imp_scores),
                'n_train': int(train_scores.size),
                'n_test': int(test_scores.size),
                'n_imp': int(imp_scores.size),
            })

            if options['per_subject']:
                self.stdout.write(
                    f'[{subject}] '
                    f'train_acc={self._p(tr_acc)} test_acc={self._p(te_acc)} '
                    f'test_FAR={self._p(te_far)} test_FRR={self._p(te_frr)} '
                    f'AUC={self._p(_auc(test_scores, imp_scores))} '
                    f'score(gen_te={np.mean(test_scores):+.3f}, '
                    f'imp={np.mean(imp_scores) if imp_scores.size else float("nan"):+.3f})'
                )

        if not rows:
            raise CommandError('No se evaluó ningún modelo.')

        self._summary(rows, threshold)

    @staticmethod
    def _p(value):
        return 'n/a' if value is None else f'{value * 100:.2f}%'

    @staticmethod
    def _avg(values):
        values = [v for v in values if v is not None]
        return sum(values) / len(values) if values else None

    def _summary(self, rows, threshold):
        n = len(rows)
        tr_far = self._avg([r['train_far'] for r in rows])
        tr_frr = self._avg([r['train_frr'] for r in rows])
        tr_acc = self._avg([r['train_acc'] for r in rows])
        te_far = self._avg([r['test_far'] for r in rows])
        te_frr = self._avg([r['test_frr'] for r in rows])
        te_acc = self._avg([r['test_acc'] for r in rows])
        eer = self._avg([r['eer']['eer'] if r['eer'] else None for r in rows])
        auc = self._avg([r['auc'] for r in rows])
        tr_accept = self._avg([r['train_accept'] for r in rows])
        te_accept = self._avg([r['test_accept'] for r in rows])
        tr_smean = self._avg([r['train_score_mean'] for r in rows])
        te_smean = self._avg([r['test_score_mean'] for r in rows])
        imp_smean = self._avg([r['imp_score_mean'] for r in rows])

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Evaluación de {n} modelos (umbral={threshold}):'
        ))
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('  DATOS VISTOS (train):'))
        self.stdout.write(f'    Score medio genuino : {tr_smean:+.4f}' if tr_smean is not None
                          else '    Score medio genuino : n/a')
        self.stdout.write(f'    Aceptación genuinos : {self._p(tr_accept)}')
        self.stdout.write(f'    FAR                 : {self._p(tr_far)}')
        self.stdout.write(f'    FRR                 : {self._p(tr_frr)}')
        self.stdout.write(f'    Accuracy            : {self._p(tr_acc)}')
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('  DATOS NO VISTOS (test):'))
        self.stdout.write(f'    Score medio genuino : {te_smean:+.4f}' if te_smean is not None
                          else '    Score medio genuino : n/a')
        self.stdout.write(f'    Score medio impostor: {imp_smean:+.4f}' if imp_smean is not None
                          else '    Score medio impostor: n/a')
        self.stdout.write(f'    Aceptación genuinos : {self._p(te_accept)}')
        self.stdout.write(f'    FAR                 : {self._p(te_far)}')
        self.stdout.write(f'    FRR                 : {self._p(te_frr)}')
        self.stdout.write(f'    Accuracy            : {self._p(te_acc)}')
        self.stdout.write(f'    EER                 : {self._p(eer)}')
        self.stdout.write(f'    AUC-ROC             : {self._p(auc)}')
        self.stdout.write('')

        # Diagnóstico de overfitting.
        if tr_acc is not None and te_acc is not None:
            gap = (tr_acc - te_acc) * 100
            self.stdout.write(self.style.MIGRATE_HEADING('  Diagnóstico overfitting:'))
            self.stdout.write(f'    Brecha accuracy (train - test): {gap:+.2f} puntos')
            if gap > 10:
                self.stdout.write(self.style.WARNING(
                    '    -> Brecha alta: posible sobreajuste.'))
            else:
                self.stdout.write(self.style.SUCCESS(
                    '    -> Brecha baja: el modelo generaliza a datos no vistos.'))
