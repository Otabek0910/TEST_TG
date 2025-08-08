# roster/apps.py

from django.apps import AppConfig

class RosterConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'roster'
    verbose_name = 'Система табелей'
    
    def ready(self):
        """Инициализация приложения"""
        # Здесь можно добавить сигналы или другую логику инициализации
        pass