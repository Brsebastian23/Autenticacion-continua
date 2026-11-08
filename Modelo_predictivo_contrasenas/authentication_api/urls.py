from django.urls import path

from .views import (
    CursorPredictView,
    CursorRetrainView,
    CursorSyntheticDatasetView,
    MetricsCurveView,
    MetricsSummaryView,
    PredictAuthView,
    RetrainFromDatasetView,
)

app_name = 'authentication_api'

urlpatterns = [
    path('retrain/', RetrainFromDatasetView.as_view(), name='retrain'),
    path('predict/', PredictAuthView.as_view(), name='predict'),
    path('metrics/summary/', MetricsSummaryView.as_view(), name='metrics-summary'),
    path('metrics/curve/', MetricsCurveView.as_view(), name='metrics-curve'),
    # Dinámica del cursor (mouse dynamics), independiente del tecleo.
    path('cursor/retrain/', CursorRetrainView.as_view(), name='cursor-retrain'),
    path('cursor/predict/', CursorPredictView.as_view(), name='cursor-predict'),
    path('cursor/synthetic/', CursorSyntheticDatasetView.as_view(),
         name='cursor-synthetic'),
]
