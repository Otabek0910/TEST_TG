"""
Бизнес-логика приложения
"""

from .user_service import UserService
from .admin_service import AdminService
from .menu_service import MenuService

__all__ = ['UserService', 'AdminService', 'MenuService']