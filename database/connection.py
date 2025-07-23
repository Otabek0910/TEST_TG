"""
Управление подключениями к базе данных - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""

import logging
import asyncio
from typing import Optional
import psycopg2
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Менеджер подключений к PostgreSQL"""
    
    def __init__(self):
        self.connection_url = DATABASE_URL
        self._connection_pool = None
        
    async def initialize(self):
        """Инициализация connection pool (пока заглушка)"""
        logger.info("📊 Database manager инициализирован")
        # TODO: В будущем здесь будет asyncpg connection pool
        
    async def close(self):
        """Закрытие всех соединений"""
        logger.info("📊 Database connections закрыты")
        # TODO: Закрытие connection pool
        
    def get_sync_connection(self):
        """Получение синхронного подключения (временное решение)"""
        try:
            return psycopg2.connect(self.connection_url)
        except Exception as e:
            logger.error(f"Ошибка подключения к БД: {e}")
            raise

# ДОБАВЛЯЕМ ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР для импорта
db_manager = DatabaseManager()