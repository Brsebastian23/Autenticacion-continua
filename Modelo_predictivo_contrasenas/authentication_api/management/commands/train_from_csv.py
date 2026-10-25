
"""Entrena el modelo IsolationForest de uno o varios usuarios a partir del
dataset CMU DSL-StrongPasswordData.csv.

Por defecto se hace un split POR SESIÓN para evitar overfitting:
- Entrenamiento: sesiones en --train-sessions (por defecto 1..6).
- Evaluación: el resto de sesiones del usuario (por defecto 7 y 8), NUNCA usadas
  para entrenar, más impostores (otros sujetos de las mismas sesiones) para
  calcular FAR (tasa de falsa aceptación) y FRR (tasa de falso rechazo).

Uso:
    python manage.py train_from_csv                    # entrena + evalúa todos los sujetos
    python manage.py train_from_csv --subject s002     # solo un sujeto
    python manage.py train_from_csv --train-sessions 1-7
    python manage.py train_from_csv --no-eval          # entrena con TODAS las sesiones
    python manage.py train_from_csv --limit 20
"""

import csv
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from authentication_api.ml_service import (
    FEATURE_COLUMNS,
    MLServiceError,
    evaluate_model,
    load_model,
    train_model,
)
from authentication_api.models import UserProfile

META_COLUMNS = {'subject', 'sessionIndex', 'rep'}

# Sesiones usadas para entrenar por defecto (el resto se reserva para evaluación).
DEFAULT_TRAIN_SESSIONS = '1-6'


def _parse_sessions(value):
    """Convierte '1-6,8' en {1, 2, 3, 4, 5, 6, 8}."""
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


def _fmt_pct(value):
    return 'n/a' if value is None else f'{value * 100:.2f}%'


class Command(BaseCommand):
    help = 'Entrena modelos IsolationForest por usuario desde DSL-StrongPasswordData.csv'

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
            help='Sujeto a entrenar (p. ej. s002). Se puede repetir.',
        )
        parser.add_argument(
            '--train-sessions',
            default=DEFAULT_TRAIN_SESSIONS,
            help=(
                'Sesiones para entrenar, p. ej. "1-6" o "1,3,5" '
                f'(por defecto: {DEFAULT_TRAIN_SESSIONS}). '
                'El resto de sesiones se usa para evaluar si no se pasa --no-eval.'
            ),
        )
        parser.add_argument(
            '--no-eval',
            action='store_true',
            help='No hacer split: entrena con TODAS las sesiones y no evalúa.',
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=float(settings.ML_DECISION_THRESHOLD),
            help='Umbral de decisión para la evaluación (por defecto: ML_DECISION_THRESHOLD).',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Máximo de sujetos a procesar.',
        )

    def handle(self, *args, **options):
        dataset_path = Path(options['dataset'])
        if not dataset_path.exists():
            raise CommandError(f'No se encontró el dataset en {dataset_path}')

        no_eval = options['no_eval']
        train_sessions = _parse_sessions(options['train_sessions'])
        threshold = options['threshold']

        # records_by_subject[subject][session] = [records...]
        records_by_subject = defaultdict(lambda: defaultdict(list))

        with dataset_path.open(newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            missing = [col for col in FEATURE_COLUMNS if col not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(f'Faltan columnas en el CSV: {missing}')

            subjects_filter = set(options['subject']) if options['subject'] else None

            for row in reader:
                subject = row['subject']
                if subjects_filter and subject not in subjects_filter:
                    continue
                try:
                    record = {col: float(row[col]) for col in FEATURE_COLUMNS}
                except (TypeError, ValueError):
                    self.stderr.write(f'Fila inválida para {subject}, se omite.')
                    continue
                session = int(row['sessionIndex'])
                records_by_subject[subject][session].append(record)

        if not records_by_subject:
            raise CommandError('No se encontraron registros para los filtros indicados.')

        subjects = sorted(records_by_subject)
        if options['limit']:
            subjects = subjects[:options['limit']]

        trained = 0
        evaluation_rows = []

        for subject in subjects:
            by_session = records_by_subject[subject]

            if no_eval:
                train_records = [r for recs in by_session.values() for r in recs]
                eval_records = []
            else:
                train_records = [
                    r for sess, recs in by_session.items()
                    if sess in train_sessions for r in recs
                ]
                eval_records = [
                    r for sess, recs in by_session.items()
                    if sess not in train_sessions for r in recs
                ]

            if len(train_records) < 3:
                self.stderr.write(
                    f'[{subject}] ERROR: solo {len(train_records)} muestras de entrenamiento; '
                    f'revisa --train-sessions.'
                )
                continue

            try:
                result = train_model(subject, train_records)
            except MLServiceError as exc:
                self.stderr.write(f'[{subject}] ERROR: {exc}')
                continue

            UserProfile.objects.update_or_create(
                user_id=subject,
                defaults={
                    'model_trained_at': timezone.now(),
                    'training_samples': result['samples'],
                },
            )
            trained += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'[{subject}] entrenado con {result["samples"]} muestras '
                    f'-> {result["model_file"]} ({result["latency_ms"]} ms)'
                )
            )

            # Evaluación con sesiones no vistas + impostores de otros sujetos.
            if not no_eval and eval_records:
                impostors = [
                    r
                    for other in subjects if other != subject
                    for sess, recs in records_by_subject[other].items()
                    if sess not in train_sessions
                    for r in recs
                ]
                model = load_model(subject)
                metrics = evaluate_model(model, eval_records, impostors, threshold=threshold)
                evaluation_rows.append((subject, metrics))
                self.stdout.write(
                    f'    eval: FAR={_fmt_pct(metrics["far"])} '
                    f'FRR={_fmt_pct(metrics["frr"])} '
                    f'ACC={_fmt_pct(metrics["accuracy"])} '
                    f'(genuine={metrics["n_genuine"]}, impostor={metrics["n_impostor"]})'
                )

        self.stdout.write(self.style.SUCCESS(f'Modelos entrenados: {trained}/{len(subjects)}'))

        if evaluation_rows:
            self._print_summary(evaluation_rows, threshold)

    def _print_summary(self, rows, threshold):
        fars = [m['far'] for _, m in rows if m['far'] is not None]
        frrs = [m['frr'] for _, m in rows if m['frr'] is not None]
        accs = [m['accuracy'] for _, m in rows if m['accuracy'] is not None]
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Resumen de evaluación (umbral={threshold}) sobre {len(rows)} sujetos:'
        ))
        self.stdout.write(f'  FAR medio : {_fmt_pct(sum(fars) / len(fars)) if fars else "n/a"}')
        self.stdout.write(f'  FRR medio : {_fmt_pct(sum(frrs) / len(frrs)) if frrs else "n/a"}')
        self.stdout.write(f'  Accuracy  : {_fmt_pct(sum(accs) / len(accs)) if accs else "n/a"}')
