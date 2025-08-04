"""
Database layer для Telegram бота
"""

from .connection import DatabaseManager
from .queries import db_query, db_execute, db_query_single

# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()

__all__ = ['db_manager', 'db_query', 'db_execute', 'db_query_single']