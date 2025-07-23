"""
Handlers для авторизации (простые, без ConversationHandler)
"""

import logging

logger = logging.getLogger(__name__)

# Убираем старые handlers - теперь авторизация работает через ConversationHandler

def register_auth_handlers(application):
    """Регистрация handlers авторизации"""
    # ConversationHandler регистрируется отдельно в app.py
    logger.info("✅ Auth handlers зарегистрированы (через ConversationHandler)")