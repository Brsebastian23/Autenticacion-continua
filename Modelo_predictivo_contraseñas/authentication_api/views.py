import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .ml_service import FEATURE_COLUMNS, MLServiceError, predict, train_model
from .models import AuthInferenceLog, UserProfile

logger = logging.getLogger(__name__)


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
