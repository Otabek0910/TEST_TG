# database/connection.py
import asyncpg
import psycopg2
import logging
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Универсальный менеджер для управления соединениями PostgreSQL (ASYNC + SYNC).
    """
    _async_pool = None

    @classmethod
    async def initialize(cls):
        """Инициализирует асинхронный пул соединений."""
        if cls._async_pool:
            logger.warning("Асинхронный пул соединений уже инициализирован.")
            return
        try:
            cls._async_pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=5,
                max_size=20
            )
            logger.info("✅ Асинхронный пул соединений с БД успешно создан.")
        except Exception as e:
            logger.critical(f"❌ Не удалось создать асинхронный пул соединений с БД: {e}")
            raise

    @classmethod
    async def get_async_pool(cls):
        """Возвращает активный асинхронный пул соединений."""
        if cls._async_pool is None:
            await cls.initialize()
        return cls._async_pool

    @classmethod
    def get_sync_connection(cls):
        """Возвращает синхронное соединение psycopg2 для блокирующих операций."""
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception as e:
            logger.error(f"Ошибка создания синхронного соединения: {e}")
            raise

    @classmethod
    async def close(cls):
        """Закрывает все пулы соединений."""
        if cls._async_pool:
            await cls._async_pool.close()
            cls._async_pool = None
            logger.info("✅ Асинхронный пул соединений с БД закрыт.")

# Создаем единый экземпляр для всего приложения
db_manager = DatabaseManager()