"""
Handlers для Telegram бота
"""

def register_all_handlers(application):
    """Регистрация всех handlers в приложении"""
    # Импортируем здесь для избежания циклических импортов
    from .common import register_common_handlers
    from .auth import register_auth_handlers
    from .approval import register_approval_handlers
    from .workflow import register_workflow_handlers
    
    register_common_handlers(application)
    register_auth_handlers(application)
    register_approval_handlers(application)
    register_workflow_handlers(application)

__all__ = ['register_all_handlers']