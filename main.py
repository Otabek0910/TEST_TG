#!/usr/bin/env python3
"""
Точка входа Telegram бота для управления строительными отчетами
ИСПРАВЛЕНО для PTB v20 с правильной обработкой сигналов
"""

import logging
import sys
import asyncio
import signal

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

# Глобальная переменная для graceful shutdown
shutdown_event = None

def signal_handler():
    """Обработчик сигналов для graceful shutdown"""
    logger.info("🛑 Получен сигнал остановки, завершаем работу...")
    if shutdown_event:
        shutdown_event.set()

async def main():
    """Главная функция запуска приложения"""
    global shutdown_event
    shutdown_event = asyncio.Event()
    
    try:
        # Проверяем настройки
        from config.settings import TOKEN
        logger.info("✅ Конфигурация загружена успешно")

        # Инициализируем БД
        from database.migrations import run_all_migrations
        if not await run_all_migrations():
            logger.critical("❌ Ошибка инициализации БД")
            sys.exit(1)

        # Настраиваем обработку сигналов для graceful shutdown
        if sys.platform != "win32":
            # Unix/Linux системы
            for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGABRT):
                try:
                    asyncio.get_running_loop().add_signal_handler(sig, signal_handler)
                except NotImplementedError:
                    # Некоторые event loop не поддерживают signal handlers
                    logger.warning(f"⚠️ Signal handler для {sig} не поддерживается")
        else:
            # Windows - используем альтернативный подход
            logger.info("🪟 Windows система - используем KeyboardInterrupt для остановки")

        # Импортируем и запускаем бота
        from bot.app import run_bot
        logger.info("🚀 Запуск бота...")
        
        # Запускаем бот с graceful shutdown
        bot_task = asyncio.create_task(run_bot())
        
        # Ждем либо завершения бота, либо сигнала остановки
        try:
            await asyncio.wait_for(bot_task, timeout=None)
        except asyncio.CancelledError:
            logger.info("🔄 Задача бота была отменена")
        except Exception as e:
            logger.error(f"❌ Ошибка в работе бота: {e}")
            
    except (ValueError, ImportError) as e:
        logger.critical(f"❌ Ошибка конфигурации или импорта: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("🛑 Получен Ctrl+C, завершаем работу...")
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {e}")
        raise
    finally:
        # Очистка ресурсов
        logger.info("🧹 Очистка ресурсов...")
        
        # Закрываем соединение с БД если оно открыто
        try:
            from database.connection import db_manager
            await db_manager.close()
            logger.info("✅ Соединение с БД закрыто")
        except Exception as e:
            logger.error(f"⚠️ Ошибка при закрытии БД: {e}")

if __name__ == "__main__":
    try:
        # Для Windows устанавливаем политику event loop
        if sys.platform == "win32":
            # Используем WindowsSelectorEventLoopPolicy для лучшей совместимости
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Запускаем основную функцию
        asyncio.run(main())
        
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.critical(f"❌ Фатальная ошибка при запуске: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Программа завершена")