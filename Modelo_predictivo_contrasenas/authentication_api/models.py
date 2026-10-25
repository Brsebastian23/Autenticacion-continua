from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """Perfil de usuario biométrico (keystroke dynamics)."""
    user_id = models.CharField(
        max_length=64,
        primary_key=True,
        help_text='Identificador del usuario (p. ej. "s002" del dataset CMU).',
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    # Metadatos del modelo entrenado
    model_trained_at = models.DateTimeField(null=True, blank=True)
    training_samples = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'user_profile'
        ordering = ['user_id']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return self.user_id


class AuthInferenceLog(models.Model):
    """Auditoría de cada inferencia realizada por el modelo de autenticación."""

    class StatusCode(models.TextChoices):
        LEGITIMATE = 'LEGITIMATE', 'Autenticado'
        ANOMALY = 'ANOMALY', 'Anomalía detectada'
        ERROR = 'ERROR', 'Error en la inferencia'

    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='inference_logs',
        db_column='user_id',
    )
    confidence_score = models.FloatField(
        help_text='Score crudo de decision_function del IsolationForest.',
    )
    is_legitimate = models.BooleanField(default=False)
    status_code = models.CharField(
        max_length=16,
        choices=StatusCode.choices,
        default=StatusCode.ERROR,
        db_index=True,
    )
    latency_ms = models.FloatField(null=True, blank=True)
    detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = 'auth_inference_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status_code']),
        ]
        verbose_name = 'Auth Inference Log'
        verbose_name_plural = 'Auth Inference Logs'

    def __str__(self):
        return f'{self.user_id} - {self.status_code} ({self.confidence_score:.4f})'
