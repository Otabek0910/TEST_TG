# bot/app.py

"""
Основной модуль Telegram бота - ИСПРАВЛЕННАЯ ВЕРСИЯ (убран auth_flow)
"""

import logging
import asyncio
import sys
from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import TOKEN, OWNER_ID, DATABASE_URL
from database.connection import db_manager
from bot.handlers.common import register_common_handlers
from bot.handlers.workflow import register_workflow_handlers, create_rejection_conversation
from bot.handlers.approval import register_approval_handlers
from bot.handlers.analytics import register_analytics_handlers
from bot.handlers.admin import register_admin_handlers, create_admin_management_conversation, create_db_restore_conversation, create_hr_date_conversation
from bot.handlers.auth_new import register_new_auth_handlers  # CHANGED: используем auth_new напрямую
from bot.conversations.report_flow import create_report_conversation
from bot.conversations.roster_flow import create_roster_conversation

logger = logging.getLogger(__name__)

async def run_bot():
    """Запуск Telegram бота - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    logger.info("=" * 50)
    logger.info("🚀 БОТ ЗАПУСКАЕТСЯ...")
    logger.info(f"🗄️ База данных: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'локальная'}")
    logger.info(f"👑 Owner ID: {OWNER_ID}")
    logger.info("=" * 50)

    # Инициализируем БД сразу
    await db_manager.initialize()
    logger.info("✅ Database инициализирована")

    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    register_common_handlers(application)
    register_new_auth_handlers(application)
    register_approval_handlers(application)
    register_workflow_handlers(application)
    register_analytics_handlers(application)
    register_admin_handlers(application)

    # ConversationHandlers
    application.add_handler(create_report_conversation())
    application.add_handler(create_roster_conversation())
    application.add_handler(create_rejection_conversation())
    application.add_handler(create_admin_management_conversation())
    application.add_handler(create_db_restore_conversation())
    application.add_handler(create_hr_date_conversation())

    logger.info("✅ Все обработчики зарегистрированы")
    
    # Настройка планировщика
    scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
    try:
        from services.notification_service import NotificationService
        scheduler.add_job(NotificationService.process_scheduled_notifications, 'cron', hour=8, minute=0, args=[application])
        scheduler.add_job(NotificationService.send_pending_report_reminders, 'cron', hour=10, minute=0, args=[application.bot])
        scheduler.start()
        logger.info("✅ Планировщик уведомлений запущен")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка запуска планировщика: {e}")

    try:
        # FIXED: Прямое управление Application без вложенных event loops
        logger.info("🚀 Запускаем polling...")
        
        async with application:
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            
            # Простое ожидание бесконечного цикла
            try:
                await asyncio.Future()  # Ждем до прерывания
            except asyncio.CancelledError:
                pass
                
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал завершения...")
    finally:
        # Очистка ресурсов в правильном порядке
        logger.info("🔄 Очистка ресурсов...")
        
        # 1. Останавливаем планировщик
        try:
            if 'scheduler' in locals() and scheduler.running:
                scheduler.shutdown()
                logger.info("✅ Планировщик остановлен")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка остановки планировщика: {e}")
        
        # 2. Закрываем БД
        try:
            await db_manager.close()
            logger.info("✅ База данных отключена")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка закрытия БД: {e}")
            
        logger.info("🔻 Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except Exception as e:
        logger.error(f"💥 Ошибка запуска: {e}")
        sys.exit(1)