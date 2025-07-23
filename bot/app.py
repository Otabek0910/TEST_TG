# bot/app.py

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config.settings import TOKEN, OWNER_ID
from database.connection import db_manager

logger = logging.getLogger(__name__)

# --- ТЕСТОВЫЙ ОБРАБОТЧИК ---
async def minimal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот запущен в минимальном режиме. Ошибки нет.")

async def run_bot():
    """МИНИМАЛЬНЫЙ ЗАПУСК БОТА ДЛЯ ДИАГНОСТИКИ"""
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК В МИНИМАЛЬНОМ РЕЖИМЕ ДИАГНОСТИКИ...")
    logger.info(f"👑 Owner ID: {OWNER_ID}")
    logger.info("=" * 50)

    builder = Application.builder().token(TOKEN)
    application = builder.build()

    # --- ВРЕМЕННО ОТКЛЮЧАЕМ ВСЕ СЛОЖНЫЕ КОМПОНЕНТЫ ---
    # async def post_init(app: Application) -> None:
    #     await db_manager.initialize()
    #     logger.info("✅ Database инициализирована")
    #
    # async def post_stop(app: Application) -> None:
    #     await db_manager.close()
    #     logger.info("✅ Ресурсы освобождены")
    #
    # application.post_init = post_init
    # application.post_stop = post_stop
    
    # --- РЕГИСТРИРУЕМ ТОЛЬКО ОДИН ПРОСТОЙ ОБРАБОТЧИК ---
    application.add_handler(CommandHandler("start", minimal_start))
    logger.info("✅ Зарегистрирован только тестовый обработчик /start")

    logger.info("🚀 Бот готов к работе!")
    await application.run_polling(drop_pending_updates=True)