# services/__init__.py

"""
Бизнес-логика приложения
"""

# FIXED: Убираем импорты, которые могут вызывать циклические зависимости
# Оставляем только базовые сервисы без зависимостей от bot.handlers

from .user_service import UserService
from .admin_service import AdminService

# REMOVED: MenuService вызывает циклический импорт через bot.middleware.security
# Его нужно импортировать напрямую где используется

__all__ = ['UserService', 'AdminService']