# main.py

"""
Главный модуль запуска Telegram бота - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""

import sys
import asyncio
import logging
import signal
from pathlib import Path

# Добавляем текущую директорию в Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Главная асинхронная функция"""
    logger.info("✅ Конфигурация загружена успешно")
    
    try:
        # Инициализация БД и миграции
        from database.migrations import run_all_migrations
        await run_all_migrations()
        
        # Запуск бота
        from bot.app import run_bot
        logger.info("🚀 Запуск бота...")
        await run_bot()
        
    except KeyboardInterrupt:
        logger.info("🛑 Получен Ctrl+C, завершаем работу...")
    except Exception as e:
        logger.error(f"❌ Ошибка в работе бота: {e}")
        raise

if __name__ == "__main__":
    # FIXED: Для Windows - правильная политика event loop
    if sys.platform == "win32":
        # Устанавливаем правильную политику для Windows
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError:
            # Fallback для старых версий Python
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        # FIXED: Простой запуск без дополнительной обработки сигналов
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"❌ Фатальная ошибка при запуске: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Программа завершена")