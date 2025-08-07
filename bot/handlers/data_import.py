# bot/handlers/data_import.py

import logging
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.middleware.security import check_user_role
from services.import_service import ImportService
from utils.chat_utils import auto_clean
from utils.localization import get_user_language, get_text
from utils.constants import TEMP_DIR

logger = logging.getLogger(__name__)

@auto_clean
async def handle_directories_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает загруженный Excel-файл со справочниками"""
    
    # Проверяем тип файла
    excel_mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if not update.message.document or update.message.document.mime_type != excel_mime_type:
        return  # Игнорируем не-Excel файлы
    
    user_id = str(update.effective_user.id)
    user_role = check_user_role(user_id)
    
    # Проверяем права доступа
    if not user_role.get('isAdmin'):
        await update.message.reply_text("⛔️ У вас нет прав для загрузки справочников.")
        return
    
    # Уведомляем о начале обработки
    processing_message = await update.message.reply_text(
        "✅ Файл получен. Начинаю обработку справочников...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    file_path = None
    
    try:
        # Создаем временную директорию
        ImportService.create_temp_directory()
        
        # Скачиваем файл
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = os.path.join(TEMP_DIR, f"upload_{file.file_id}.xlsx")
        await file.download_to_drive(file_path)
        
        logger.info(f"Файл справочников загружен: {file_path}")
        
        # Обрабатываем файл через сервис
        result = ImportService.import_directories_from_excel(file_path)
        
        # Форматируем результат
        summary_text = ImportService.format_import_summary(result)
        
        # Отправляем результат
        await processing_message.edit_text(
            summary_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Логируем результат
        if result['success']:
            counters = result['counters']
            logger.info(f"Импорт справочников успешно завершен пользователем {user_id}: "
                       f"дисциплины +{counters['disciplines']}, "
                       f"корпуса {counters['objects']}, "
                       f"виды работ {counters['work_types']}")
        else:
            logger.error(f"Ошибка импорта справочников пользователем {user_id}: {result.get('error')}")
        
    except Exception as e:
        logger.error(f"Критическая ошибка при обработке Excel-файла справочников от {user_id}: {e}")
        
        try:
            await processing_message.edit_text(
                "❌ Произошла критическая ошибка при обработке файла. "
                "Убедитесь, что структура файла соответствует шаблону.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as edit_error:
            # Если не удалось отредактировать сообщение, отправляем новое
            await update.message.reply_text(
                "❌ Произошла критическая ошибка при обработке файла.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    finally:
        # Очищаем временный файл
        if file_path:
            ImportService.cleanup_temp_file(file_path)

async def handle_database_restore_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает файл для полного восстановления БД (только для владельца)"""
    from config.settings import OWNER_ID
    
    user_id = str(update.effective_user.id)
    
    # Только владелец может восстанавливать БД
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔️ Только владелец бота может восстанавливать БД.")
        return
    
    # Проверяем тип файла
    excel_mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if not update.message.document or update.message.document.mime_type != excel_mime_type:
        await update.message.reply_text("❌ Для восстановления БД требуется Excel файл.")
        return
    
    # Предупреждение о том, что данные будут удалены
    warning_message = await update.message.reply_text(
        "⚠️ **ВНИМАНИЕ!** Вы собираетесь восстановить БД из файла.\n"
        "**ВСЕ ТЕКУЩИЕ ДАННЫЕ БУДУТ УДАЛЕНЫ!**\n\n"
        "Для подтверждения отправьте сообщение: `CONFIRM RESTORE`",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Сохраняем файл для последующей обработки
    try:
        ImportService.create_temp_directory()
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = os.path.join(TEMP_DIR, f"restore_db_{user_id}.xlsx")
        await file.download_to_drive(file_path)
        
        # Сохраняем путь к файлу в контексте пользователя
        context.user_data['pending_restore_file'] = file_path
        
        logger.info(f"Файл для восстановления БД загружен от владельца {user_id}: {file_path}")
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке файла для восстановления БД: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при загрузке файла.",
            parse_mode=ParseMode.MARKDOWN
        )

async def handle_restore_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает подтверждение восстановления БД"""
    from config.settings import OWNER_ID
    
    user_id = str(update.effective_user.id)
    
    # Только владелец может восстанавливать БД
    if user_id != OWNER_ID:
        return
    
    # Проверяем команду подтверждения
    if update.message.text != "CONFIRM RESTORE":
        return
    
    # Проверяем, есть ли файл для восстановления
    file_path = context.user_data.get('pending_restore_file')
    if not file_path or not os.path.exists(file_path):
        await update.message.reply_text(
            "❌ Файл для восстановления не найден. Загрузите файл заново.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Начинаем восстановление
    processing_message = await update.message.reply_text(
        "🔄 **Начинаю полное восстановление БД...**\n"
        "⏳ Это может занять несколько минут.",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        # Выполняем восстановление
        result = ImportService.restore_full_database_from_excel(file_path)
        
        # Форматируем результат
        summary_text = ImportService.format_restore_summary(result)
        
        # Отправляем результат
        await processing_message.edit_text(
            summary_text,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Логируем результат
        if result['success']:
            restored_count = len(result.get('restored_tables', []))
            logger.info(f"Полное восстановление БД завершено владельцем {user_id}: восстановлено {restored_count} таблиц")
        else:
            logger.error(f"Ошибка восстановления БД владельцем {user_id}: {result.get('error')}")
        
        # Очищаем контекст
        context.user_data.pop('pending_restore_file', None)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при восстановлении БД: {e}")
        
        try:
            await processing_message.edit_text(
                "❌ Произошла критическая ошибка при восстановлении БД. "
                "Проверьте логи для подробностей.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await update.message.reply_text(
                "❌ Критическая ошибка при восстановлении БД.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    finally:
        # Очищаем временный файл
        if file_path:
            ImportService.cleanup_temp_file(file_path)

def register_import_handlers(application):
    """Регистрация обработчиков импорта"""
    
    # Обработчик Excel файлов (справочники)
    application.add_handler(
        MessageHandler(
            filters.Document.MimeType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            handle_directories_excel
        )
    )
    
    # Обработчик подтверждения восстановления БД
    application.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(r'^CONFIRM RESTORE$'),
            handle_restore_confirmation
        )
    )
    
    logger.info("✅ Import handlers зарегистрированы")