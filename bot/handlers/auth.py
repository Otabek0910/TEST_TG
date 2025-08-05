# bot/handlers/auth.py

"""
Handlers для авторизации - ОБНОВЛЕННАЯ ВЕРСИЯ
"""

import logging

logger = logging.getLogger(__name__)

def register_auth_handlers(application):
    """Регистрация handlers авторизации - используем auth_new.py"""
    from .auth_new import register_new_auth_handlers
    register_new_auth_handlers(application)
    logger.info("✅ Auth handlers зарегистрированы (через auth_new)")