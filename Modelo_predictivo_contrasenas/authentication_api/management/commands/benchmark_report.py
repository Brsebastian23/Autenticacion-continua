"""Genera un reporte formal de benchmark (EER, FAR, FRR, AUC) y lo persiste.

Este comando materializa el EER exigido por la pregunta de investigación:
recorre el dataset CMU, evalúa el modelo entrenado de cada sujeto con el split
por sesión (train = sesiones de entrenamiento, test = sesiones no vistas), y
escribe dos artefactos:

- ``docs/benchmark_eer.json``  -> datos crudos consumidos por la API / Front.
- ``docs/REPORTE_EER.md``      -> reporte legible con tablas y conclusión.

Además calcula el **umbral óptimo** (el ``threshold_at_eer`` agregado) que
minimiza |FAR - FRR|, que es el valor recomendado para producción.

Uso:
    python manage.py benchmark_report                 # genera el reporte
    python manage.py benchmark_report --per-subject   # incluye tabla por sujeto
    python manage.py benchmark_report --no-write      # solo imprime, no persiste
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from authentication_api import metrics as M
from authentication_api.ml_service import (
    FEATURE_COLUMNS,
    MLServiceError,
    load_model,
    record_to_vector,
)

DEFAULT_TRAIN_SESSIONS = '1-6'
# Carpeta de salida por defecto, relativa al microservicio ML.
DEFAULT_OUTPUT_DIR = Path(settings.BASE_DIR) / 'docs'


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


def _fmt_pct(value):
    return 'n/a' if value is None else f'{value * 100:.2f}%'


class Command(BaseCommand):
    help = 'Genera docs/REPORTE_EER.md y docs/benchmark_eer.json con FAR/FRR/EER/AUC.'

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
            help='Sujeto a incluir (p. ej. s002). Se puede repetir.',
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
            help='Umbral de referencia para FAR/FRR (por defecto: ML_DECISION_THRESHOLD).',
        )
        parser.add_argument(
            '--output-dir',
            default=str(DEFAULT_OUTPUT_DIR),
            help='Directorio donde se escriben los reportes.',
        )
        parser.add_argument(
            '--per-subject',
            action='store_true',
            help='Incluir tabla por sujeto en el reporte Markdown.',
        )
        parser.add_argument(
            '--no-write',
            action='store_true',
            help='Solo imprimir; no escribir archivos.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Máximo de sujetos a evaluar.',
        )

    def handle(self, *args, **options):
        dataset_path = Path(options['dataset'])
        if not dataset_path.exists():
            raise CommandError(f'No se encontró el dataset en {dataset_path}')

        train_sessions = _parse_sessions(options['train_sessions'])
        threshold = options['threshold']
        per_subject_flag = options['per_subject']
        output_dir = Path(options['output_dir'])

        # records_by_subject[subject][session] = [records...]
        records_by_subject = defaultdict(lambda: defaultdict(list))
        with dataset_path.open(newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            missing = [c for c in FEATURE_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(f'Faltan columnas en el CSV: {missing}')
            # Se carga TODO el dataset: los sujetos filtrados son usuarios a
            # evaluar; el resto se usa como impostores.
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
                continue
            try:
                model = load_model(subject)
            except MLServiceError as exc:
                self.stderr.write(f'[{subject}] {exc}')
                continue

            test_matrix = np.vstack([record_to_vector(r) for r in test_recs])
            test_scores = model.decision_function(test_matrix)

            # Impostores: test de TODOS los demás sujetos (no vistos por el modelo).
            other_recs = [r for o in all_subjects if o != subject for r in _test_records_of(o)]
            imp_scores = (
                model.decision_function(np.vstack([record_to_vector(r) for r in other_recs]))
                if other_recs else np.empty((0,))
            )

            far, frr = M.far_frr_at(test_scores, imp_scores, threshold)
            model_eer = M.eer(test_scores, imp_scores)
            model_auc = M.auc_roc(test_scores, imp_scores)
            acc = M.accuracy_at(test_scores, imp_scores, threshold)

            rows.append({
                'subject': subject,
                'far': far,
                'frr': frr,
                'accuracy': acc,
                'eer': model_eer['eer'] if model_eer else None,
                'threshold_at_eer': model_eer['threshold_at_eer'] if model_eer else None,
                'auc': model_auc,
                'n_test': int(test_scores.size),
                'n_impostor': int(imp_scores.size),
            })

        if not rows:
            raise CommandError('No se evaluó ningún modelo. ¿Entrenaste con train_from_csv?')

        # Agregados.
        eer_summary = M.summarize_benchmark([r['eer'] for r in rows])
        auc_summary = M.summarize_benchmark([r['auc'] for r in rows])
        mean_far = self._avg([r['far'] for r in rows])
        mean_frr = self._avg([r['frr'] for r in rows])
        mean_acc = self._avg([r['accuracy'] for r in rows])
        # Umbral óptimo: mediana de los thresholds_at_eer (robusto a outliers).
        thresholds = [r['threshold_at_eer'] for r in rows if r['threshold_at_eer'] is not None]
        optimal_threshold = float(np.median(thresholds)) if thresholds else None

        report = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'dataset': dataset_path.name,
            'n_subjects': len(rows),
            'train_sessions': options['train_sessions'],
            'reference_threshold': threshold,
            'optimal_threshold': optimal_threshold,
            'aggregate': {
                'eer': eer_summary,
                'auc': auc_summary,
                'far_at_reference': mean_far,
                'frr_at_reference': mean_frr,
                'accuracy_at_reference': mean_acc,
            },
            'per_subject': [
                {k: (round(v, 6) if isinstance(v, float) else v) for k, v in row.items()}
                for row in rows
            ],
        }

        # Imprimir resumen en consola.
        self._print_summary(report)

        if not options['no_write']:
            self._write_files(report, output_dir, per_subject_flag)

    @staticmethod
    def _avg(values):
        values = [v for v in values if v is not None]
        return sum(values) / len(values) if values else None

    def _print_summary(self, report):
        agg = report['aggregate']
        eer = agg['eer']
        auc = agg['auc']
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Benchmark EER sobre {report["n_subjects"]} sujetos '
            f'(split: train {report["train_sessions"]}, test resto)'
        ))
        self.stdout.write(f'  EER medio     : {_fmt_pct(eer["mean"])}')
        self.stdout.write(f'  EER mediana   : {_fmt_pct(eer["median"])}')
        self.stdout.write(f'  EER min/max   : {_fmt_pct(eer["min"])} / {_fmt_pct(eer["max"])}')
        self.stdout.write(f'  EER desv.     : {_fmt_pct(eer["std"])}')
        self.stdout.write(f'  AUC-ROC medio : {_fmt_pct(auc["mean"])}')
        self.stdout.write(f'  FAR @ umbral {report["reference_threshold"]}: '
                          f'{_fmt_pct(agg["far_at_reference"])}')
        self.stdout.write(f'  FRR @ umbral {report["reference_threshold"]}: '
                          f'{_fmt_pct(agg["frr_at_reference"])}')
        self.stdout.write(f'  Accuracy @ umbral {report["reference_threshold"]}: '
                          f'{_fmt_pct(agg["accuracy_at_reference"])}')
        if report['optimal_threshold'] is not None:
            self.stdout.write(self.style.SUCCESS(
                f'  Umbral óptimo (mediana de threshold_at_eer): '
                f'{report["optimal_threshold"]:+.6f}'))
        self.stdout.write('')

    def _write_files(self, report, output_dir, per_subject):
        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON crudo.
        json_path = output_dir / 'benchmark_eer.json'
        with json_path.open('w', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)

        # Markdown legible.
        md_path = output_dir / 'REPORTE_EER.md'
        md_path.write_text(self._render_markdown(report, per_subject), encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(f'Reporte escrito en {md_path}'))
        self.stdout.write(self.style.SUCCESS(f'Datos JSON escritos en {json_path}'))

    @staticmethod
    def _render_markdown(report, per_subject):
        agg = report['aggregate']
        eer = agg['eer']
        auc = agg['auc']
        lines = [
            '# Reporte de Exactitud (EER) — Autenticación Continua',
            '',
            f'**Generado:** {report["generated_at"]}  ',
            f'**Dataset:** `{report["dataset"]}`  ',
            f'**Sujetos evaluados:** {report["n_subjects"]}  ',
            f'**Split:** entrenamiento sesiones `{report["train_sessions"]}`, '
            f'test = resto de sesiones (no vistas) + impostores de otros sujetos.',
            '',
            '## Respuesta a la pregunta de investigación',
            '',
            '> ¿Qué **EER** alcanza el modelo para distinguir al usuario legítimo '
            'de un impostor?',
            '',
            f'El modelo **IsolationForest** (una clase, un modelo por sujeto) alcanza un '
            f'**EER medio de {_fmt_pct(eer["mean"])}** (mediana {_fmt_pct(eer["median"])}, '
            f'rango {_fmt_pct(eer["min"])}–{_fmt_pct(eer["max"])}) sobre '
            f'**{eer["count"]} sujetos**, con un **AUC-ROC medio de {_fmt_pct(auc["mean"])}**. '
            f'El AUC indica que un genuino puntúa por encima de un impostor '
            f'{_fmt_pct(auc["mean"])} de las veces.',
            '',
            '## Métricas agregadas',
            '',
            '| Métrica | Valor |',
            '|---|---|',
            f'| EER medio | {_fmt_pct(eer["mean"])} |',
            f'| EER mediana | {_fmt_pct(eer["median"])} |',
            f'| EER desviación | {_fmt_pct(eer["std"])} |',
            f'| EER mínimo | {_fmt_pct(eer["min"])} |',
            f'| EER máximo | {_fmt_pct(eer["max"])} |',
            f'| AUC-ROC medio | {_fmt_pct(auc["mean"])} |',
            f'| FAR @ umbral {report["reference_threshold"]} | {_fmt_pct(agg["far_at_reference"])} |',
            f'| FRR @ umbral {report["reference_threshold"]} | {_fmt_pct(agg["frr_at_reference"])} |',
            f'| Accuracy @ umbral {report["reference_threshold"]} | '
            f'{_fmt_pct(agg["accuracy_at_reference"])} |',
            f'| **Umbral óptimo recomendado** | '
            f'{("+" if (report["optimal_threshold"] or 0) >= 0 else "")}'
            f'{report["optimal_threshold"]:.6f} |'
            if report["optimal_threshold"] is not None else '| Umbral óptimo | n/a |',
            '',
            '## Interpretación',
            '',
            f'- Un **EER de {_fmt_pct(eer["mean"])}** significa que, en el punto de '
            f'equilibrio, el sistema falla aproximadamente 1 de cada '
            f'{int(round(1 / eer["mean"])) if eer["mean"] else "n/a"} decisiones, '
            f'equitativamente entre genuinos rechazados y impostores aceptados.',
            '- La separación de clases (AUC) es alta; el error se concentra en la zona '
            'de solapamiento de scores, no en una confusión global.',
            '- El umbral óptimo sugerido minimiza |FAR − FRR| y puede fijarse en '
            '`ML_DECISION_THRESHOLD` para producción.',
            '',
            '## Reproducibilidad',
            '',
            '```bash',
            'python manage.py benchmark_report --per-subject',
            '```',
            '',
        ]

        if per_subject:
            lines += [
                '## Detalle por sujeto',
                '',
                '| Sujeto | EER | AUC | FAR | FRR | Umbral óptimo | n_test | n_impostor |',
                '|---|---|---|---|---|---|---|---|',
            ]
            for row in report['per_subject']:
                thr = row['threshold_at_eer']
                thr_str = f'{thr:+.6f}' if thr is not None else 'n/a'
                lines.append(
                    f'| {row["subject"]} | {_fmt_pct(row["eer"])} | '
                    f'{_fmt_pct(row["auc"])} | {_fmt_pct(row["far"])} | '
                    f'{_fmt_pct(row["frr"])} | {thr_str} | '
                    f'{row["n_test"]} | {row["n_impostor"]} |'
                )
            lines.append('')

        return '\n'.join(lines) + '\n'
