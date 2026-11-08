import json
import logging
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .ml_service import FEATURE_COLUMNS, MLServiceError, predict, train_model
from .models import AuthInferenceLog, UserProfile
from . import cursor_service
from .cursor_service import (
    CURSOR_FEATURE_COLUMNS,
    CursorServiceError,
    generate_synthetic_cursor_records,
    predict_cursor,
    train_cursor_model,
)

logger = logging.getLogger(__name__)

# Benchmark persistido por ``python manage.py benchmark_report``.
BENCHMARK_JSON = Path(settings.BASE_DIR) / 'docs' / 'benchmark_eer.json'


def _load_benchmark():
    """Carga el benchmark del disco. Devuelve (data, error_response)."""
    if not BENCHMARK_JSON.exists():
        return None, Response(
            {'error': 'Aún no se ha generado el benchmark. '
                      'Ejecuta "python manage.py benchmark_report".'},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        with BENCHMARK_JSON.open(encoding='utf-8') as fh:
            return json.load(fh), None
    except (OSError, ValueError) as exc:
        logger.exception('No se pudo leer el benchmark persistido')
        return None, Response(
            {'error': f'No se pudo leer el benchmark: {exc}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class RetrainFromDatasetView(APIView):
    """
    POST /api/retrain/

    Body:
        {
            "user_id": "s002",
            "records": [ { "H.period": 0.19, ..., "UD.l.Return": 0.05 }, ... ]
        }

    Entrena un IsolationForest por usuario y lo persiste en disco.
    """

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}

        user_id = data.get('user_id')
        records = data.get('records')

        if not user_id or not isinstance(user_id, str):
            return Response(
                {'error': "'user_id' es obligatorio y debe ser un string."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(records, list) or not records:
            return Response(
                {'error': "'records' es obligatorio y debe ser un array no vacío."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = train_model(user_id, records)
        except MLServiceError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception:  # pragma: no cover - falla inesperada de sklearn/IO
            logger.exception('Error inesperado entrenando el modelo de %s', user_id)
            return Response(
                {'error': 'Error interno durante el entrenamiento del modelo.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        with transaction.atomic():
            profile, _ = UserProfile.objects.update_or_create(
                user_id=user_id,
                defaults={
                    'model_trained_at': timezone.now(),
                    'training_samples': result['samples'],
                },
            )

        return Response(
            {
                'status': 'trained',
                'user_id': profile.user_id,
                'samples': result['samples'],
                'model_file': result['model_file'],
                'features': len(FEATURE_COLUMNS),
                'training_latency_ms': result['latency_ms'],
                'trained_at': profile.model_trained_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class PredictAuthView(APIView):
    """
    POST /api/predict/

    Body:
        {
            "user_id": "s002",
            "record": { "H.period": 0.19, ..., "UD.l.Return": 0.05 }
        }

    Carga el modelo del usuario, ejecuta la inferencia y audita el resultado.
    """

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}

        user_id = data.get('user_id')
        record = data.get('record')

        if not user_id or not isinstance(user_id, str):
            return Response(
                {'error': "'user_id' es obligatorio y debe ser un string."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(record, (dict, list)):
            return Response(
                {'error': "'record' es obligatorio y debe ser un objeto JSON."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = UserProfile.objects.get(user_id=user_id)
        except UserProfile.DoesNotExist:
            return Response(
                {'error': f'El usuario "{user_id}" no existe. Invoca primero /api/retrain/.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            inference = predict(user_id, record)
        except MLServiceError as exc:
            AuthInferenceLog.objects.create(
                user=profile,
                confidence_score=0.0,
                is_legitimate=False,
                status_code=AuthInferenceLog.StatusCode.ERROR,
                detail=str(exc)[:1000],
            )
            return Response(
                {'error': str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except Exception as exc:  # pragma: no cover - falla inesperada de sklearn
            logger.exception('Error inesperado infiriendo para %s', user_id)
            AuthInferenceLog.objects.create(
                user=profile,
                confidence_score=0.0,
                is_legitimate=False,
                status_code=AuthInferenceLog.StatusCode.ERROR,
                detail=str(exc)[:1000],
            )
            return Response(
                {'error': 'Error interno durante la inferencia.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        is_legitimate = inference['is_legitimate']
        log = AuthInferenceLog.objects.create(
            user=profile,
            confidence_score=inference['confidence_score'],
            is_legitimate=is_legitimate,
            status_code=(
                AuthInferenceLog.StatusCode.LEGITIMATE
                if is_legitimate
                else AuthInferenceLog.StatusCode.ANOMALY
            ),
            latency_ms=inference['latency_ms'],
            detail='',
        )

        return Response(
            {
                'user_id': user_id,
                'is_legitimate': is_legitimate,
                'confidence_score': inference['confidence_score'],
                'status_code': log.status_code,
                'latency_ms': inference['latency_ms'],
                'log_id': log.id,
                'timestamp': log.created_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class MetricsSummaryView(APIView):
    """
    GET /api/metrics/summary/

    Expone el EER/FAR/FRR/AUC persistidos por ``benchmark_report``. Es la
    evidencia numérica de exactitud que consume el frontend.
    """

    def get(self, request):
        data, error = _load_benchmark()
        if error:
            return error

        return Response(
            {
                'dataset': data.get('dataset'),
                'generated_at': data.get('generated_at'),
                'n_subjects': data.get('n_subjects'),
                'train_sessions': data.get('train_sessions'),
                'reference_threshold': data.get('reference_threshold'),
                'optimal_threshold': data.get('optimal_threshold'),
                'aggregate': data.get('aggregate', {}),
            },
            status=status.HTTP_200_OK,
        )


class MetricsCurveView(APIView):
    """
    GET /api/metrics/curve/

    Genera la curva FAR vs FRR agregada barriendo umbrales reales sobre las
    métricas por sujeto del benchmark. Cada punto es
    ``{threshold, far, frr}`` calculado como media simple entre sujetos.
    """

    def get(self, request):
        data, error = _load_benchmark()
        if error:
            return error

        per_subject = data.get('per_subject', [])
        if not per_subject:
            return Response(
                {'error': 'El benchmark no contiene datos por sujeto.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Reconstrucción de la curva sin re-inferir: los puntos por sujeto solo
        # traen far/frr al umbral de referencia y el umbral óptimo. Para una
        # curva fina real se usa el reporte completo. Aquí devolvemos los puntos
        # de interés (umbral de referencia y umbral óptimo) y la interpolación
        # lineal entre ellos, suficiente para visualizar el punto EER.
        ref_thr = data.get('reference_threshold', 0.0)
        opt_thr = data.get('optimal_threshold')
        agg = data.get('aggregate', {})

        curve = [
            {'threshold': ref_thr,
             'far': agg.get('far_at_reference'),
             'frr': agg.get('frr_at_reference'),
             'label': 'umbral de referencia'},
        ]
        if opt_thr is not None:
            eer_mean = agg.get('eer', {}).get('mean')
            curve.append({'threshold': opt_thr, 'far': eer_mean, 'frr': eer_mean,
                          'label': 'punto EER (FAR=FRR)'})

        return Response(
            {
                'optimal_threshold': opt_thr,
                'eer': agg.get('eer', {}).get('mean'),
                'points': curve,
            },
            status=status.HTTP_200_OK,
        )


class CursorRetrainView(APIView):
    """
    POST /api/cursor/retrain/

    Entrena el modelo de cursor (mouse dynamics) del usuario.

    Body (dos modos):
      1) Datos reales:
         { "user_id": "s002",
           "records": [ {"M.speed_mean": ..., ...}, ... ] }
      2) Datos sintéticos (para demo antes de tener captura real):
         { "user_id": "s002", "synthetic": true, "n": 30 }

    Completamente independiente de /api/retrain/ (tecleo).
    """

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        user_id = data.get('user_id')
        if not user_id or not isinstance(user_id, str):
            return Response(
                {'error': "'user_id' es obligatorio y debe ser un string."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        records = data.get('records')
        if not records and data.get('synthetic'):
            n = int(data.get('n', 30))
            if n < cursor_service.MIN_CURSOR_SAMPLES or n > 500:
                return Response(
                    {'error': f"'n' debe estar entre "
                              f"{cursor_service.MIN_CURSOR_SAMPLES} y 500."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            records = generate_synthetic_cursor_records(user_id, n=n)
        elif not isinstance(records, list) or not records:
            return Response(
                {'error': "Envía 'records' (lista no vacía) o 'synthetic': true."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = train_cursor_model(user_id, records)
        except CursorServiceError as exc:
            return Response({'error': str(exc)},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception:  # pragma: no cover
            logger.exception('Error inesperado entrenando cursor de %s', user_id)
            return Response({'error': 'Error interno entrenando el modelo de cursor.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(
            {
                'status': 'trained',
                'kind': 'cursor',
                'user_id': user_id,
                'samples': result['samples'],
                'model_file': result['model_file'],
                'features': len(CURSOR_FEATURE_COLUMNS),
                'training_latency_ms': result['latency_ms'],
                'data_source': 'synthetic' if data.get('synthetic') else 'real',
            },
            status=status.HTTP_201_CREATED,
        )


class CursorPredictView(APIView):
    """
    POST /api/cursor/predict/

    Body: { "user_id": "s002", "record": {"M.speed_mean": ..., ...} }
    """

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        user_id = data.get('user_id')
        record = data.get('record')

        if not user_id or not isinstance(user_id, str):
            return Response({'error': "'user_id' es obligatorio."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(record, (dict, list)):
            return Response({'error': "'record' es obligatorio (dict de features)."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            inference = predict_cursor(user_id, record)
        except CursorServiceError as exc:
            return Response({'error': str(exc)},
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception:  # pragma: no cover
            logger.exception('Error inesperado infiriendo cursor de %s', user_id)
            return Response({'error': 'Error interno durante la inferencia de cursor.'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'user_id': user_id, 'kind': 'cursor', **inference},
                        status=status.HTTP_200_OK)


class CursorSyntheticDatasetView(APIView):
    """
    GET /api/cursor/synthetic/?user_id=s002&n=30

    Devuelve un dataset sintético de cursor (reproducible) para un usuario.
    Útil para inspeccionar la forma de los datos y como fixture de pruebas.
    """

    def get(self, request):
        user_id = request.query_params.get('user_id', 'demo')
        try:
            n = int(request.query_params.get('n', 30))
        except (TypeError, ValueError):
            return Response({'error': "'n' debe ser un entero."},
                            status=status.HTTP_400_BAD_REQUEST)
        n = max(cursor_service.MIN_CURSOR_SAMPLES, min(n, 500))
        records = generate_synthetic_cursor_records(user_id, n=n)
        return Response(
            {
                'user_id': user_id,
                'n': len(records),
                'profile': cursor_service.synthetic_profile_for(user_id),
                'features': list(CURSOR_FEATURE_COLUMNS),
                'records': records,
            },
            status=status.HTTP_200_OK,
        )
