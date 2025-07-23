#!/usr/bin/env python3
"""
Точка входа Telegram бота для управления строительными отчетами
"""

import logging
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def main():
    """Главная функция запуска приложения"""
    try:
        # Проверяем настройки
        from config.settings import TOKEN
        logger.info("✅ Конфигурация загружена успешно")

        # Инициализируем БД
        from database.migrations import run_all_migrations
        if not await run_all_migrations():
            logger.critical("❌ Ошибка инициализации БД")
            sys.exit(1)

        # Импортируем и запускаем бота
        from bot.app import run_bot
        logger.info("🚀 Запуск бота...")
        await run_bot()

    except (ValueError, ImportError) as e:
        logger.critical(f"❌ Ошибка конфигурации или импорта: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # КЛЮЧЕВОЙ МОМЕНТ: Запуск асинхронной функции через asyncio.run()
    asyncio.run(main())