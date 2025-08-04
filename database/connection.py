# database/connection.py
import asyncpg
import logging
from config.settings import DATABASE_URL

logger = logging.getLogger(__name__)

class DBManager:
    """
    Асинхронный менеджер для управления пулом соединений PostgreSQL.
    """
    _pool = None

    @classmethod
    async def initialize(cls):
        """Инициализирует пул соединений."""
        if cls._pool:
            logger.warning("Пул соединений уже инициализирован.")
            return
        try:
            cls._pool = await asyncpg.create_pool(
                dsn=DATABASE_URL,
                min_size=5,
                max_size=20
            )
            logger.info("✅ Пул соединений с БД успешно создан.")
        except Exception as e:
            logger.critical(f"❌ Не удалось создать пул соединений с БД: {e}")
            raise

    @classmethod
    async def get_pool(cls):
        """Возвращает активный пул соединений."""
        if cls._pool is None:
            await cls.initialize()
        return cls._pool

    @classmethod
    async def close(cls):
        """Закрывает пул соединений."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("✅ Пул соединений с БД закрыт.")

# Создаем единый экземпляр для всего приложения
db_manager = DBManager()