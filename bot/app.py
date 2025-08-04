"""
Основной модуль Telegram бота - ИСПРАВЛЕННАЯ ВЕРСИЯ
"""

import logging
from telegram.ext import Application
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import TOKEN, OWNER_ID, DATABASE_URL
from database.connection import db_manager  # FIXED: Правильный импорт
from bot.handlers.common import register_common_handlers
from bot.handlers.workflow import register_workflow_handlers, create_rejection_conversation
from bot.handlers.approval import register_approval_handlers
from bot.handlers.analytics import register_analytics_handlers
from bot.handlers.admin import register_admin_handlers, create_admin_management_conversation, create_db_restore_conversation, create_hr_date_conversation
from bot.handlers.auth_new import register_new_auth_handlers
from bot.conversations.report_flow import create_report_conversation
from bot.conversations.roster_flow import create_roster_conversation

logger = logging.getLogger(__name__)

async def run_bot():
    """Запуск Telegram бота"""
    logger.info("=" * 50)
    logger.info("🚀 БОТ ЗАПУСКАЕТСЯ...")
    logger.info(f"🗄️ База данных: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'локальная'}")
    logger.info(f"👑 Owner ID: {OWNER_ID}")
    logger.info("=" * 50)

    builder = Application.builder().token(TOKEN)
    application = builder.build()

    async def post_init(app: Application) -> None:
        await db_manager.initialize()  # FIXED: Используем правильный метод
        logger.info("✅ Database инициализирована")
        
        scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
        from services.notification_service import NotificationService
        scheduler.add_job(NotificationService.process_scheduled_notifications, 'cron', hour=8, minute=0, args=[app])
        scheduler.add_job(NotificationService.send_pending_report_reminders, 'cron', hour=10, minute=0, args=[app.bot])
        
        app.bot_data["scheduler"] = scheduler
        logger.info("✅ Планировщик уведомлений сконфигурирован.")

    async def post_stop(app: Application) -> None:
        if "scheduler" in app.bot_data:
            app.bot_data["scheduler"].shutdown()
        await db_manager.close()
        logger.info("✅ Ресурсы освобождены")

    # Регистрация handlers
    register_common_handlers(application)
    register_workflow_handlers(application)
    register_approval_handlers(application)
    register_analytics_handlers(application)
    register_admin_handlers(application)
    register_new_auth_handlers(application)
    logger.info("✅ Обработчики зарегистрированы")

    # Регистрация conversations
    application.add_handler(create_report_conversation())
    application.add_handler(create_roster_conversation())
    application.add_handler(create_rejection_conversation())
    application.add_handler(create_admin_management_conversation())
    application.add_handler(create_db_restore_conversation())
    application.add_handler(create_hr_date_conversation())
    logger.info("✅ Конверсации зарегистрированы")

    application.post_init = post_init
    application.post_stop = post_stop
    
    logger.info("🚀 Бот готов к работе!")
    # КЛЮЧЕВОЙ МОМЕНТ: Запуск цикла бота через await
    await application.run_polling(drop_pending_updates=True)