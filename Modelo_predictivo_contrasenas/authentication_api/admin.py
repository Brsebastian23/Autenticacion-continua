from django.contrib import admin

from .models import AuthInferenceLog, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'training_samples', 'model_trained_at', 'created_at')
    search_fields = ('user_id',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AuthInferenceLog)
class AuthInferenceLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status_code', 'is_legitimate',
                    'confidence_score', 'latency_ms', 'created_at')
    list_filter = ('status_code', 'is_legitimate', 'created_at')
    search_fields = ('user__user_id',)
    readonly_fields = ('created_at',)
