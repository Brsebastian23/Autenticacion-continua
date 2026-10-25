from django.urls import path

from .views import PredictAuthView, RetrainFromDatasetView

app_name = 'authentication_api'

urlpatterns = [
    path('retrain/', RetrainFromDatasetView.as_view(), name='retrain'),
    path('predict/', PredictAuthView.as_view(), name='predict'),
]
