# bot/handlers/export.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.middleware.security import check_user_role
from services.export_service import ExportService
from utils.chat_utils import auto_clean
from utils.localization import get_user_language, get_text
from config.settings import OWNER_ID

from datetime import date, timedelta
from telegram.constants import ParseMode
import os
import gc

logger = logging.getLogger(__name__)


async def export_reports_to_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт отчетов в Excel (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = get_user_language(user_id)
    
    # Проверяем права доступа
    if not (user_role.get('isAdmin') or user_role.get('isPto') or user_role.get('isKiok') or user_role.get('isManager')):
        await query.edit_message_text("⛔️ У вас нет прав для экспорта отчетов.")
        return
    
    await query.edit_message_text("⏳ Формирую файл с отчетами... Это может занять некоторое время.")
    
    try:
        # Определяем фильтры на основе роли пользователя
        filter_params = {}
        
        # Если не админ и не менеджер 1 уровня, фильтруем по дисциплине
        if not (user_role.get('isAdmin') or user_role.get('managerLevel') == 1):
            discipline = user_role.get('discipline')
            if discipline:
                filter_params['discipline_name'] = discipline
        
        # Экспортируем данные
        file_path = ExportService.export_reports_to_excel(user_id, filter_params)
        
        if file_path:
            filename = f"Отчеты_{user_id}_{context.bot_data.get('current_date', 'export')}.xlsx"
            
            with open(file_path, 'rb') as file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file,
                    filename=filename,
                    caption="📊 Экспорт отчетов завершен"
                )
            
            # Очищаем временный файл
            ExportService.cleanup_temp_file(file_path)
            
            # Возвращаемся в меню
            keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="report_menu_all")]]
            await query.edit_message_text(
                "✅ Файл с отчетами отправлен",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text("❌ Ошибка при формировании файла. Попробуйте позже.")
            
    except Exception as e:
        logger.error(f"Ошибка экспорта отчетов для пользователя {user_id}: {e}")
        await query.edit_message_text("❌ Произошла ошибка при формировании файла.")


async def download_db_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Загрузка полного бэкапа БД (только для владельца)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    # Только владелец может скачать полный бэкап
    if user_id != OWNER_ID:
        await query.answer("⛔️ Эта команда доступна только создателю бота.", show_alert=True)
        return
    
    await query.edit_message_text("⏳ Формирую полную резервную копию... Это может занять до минуты...")
    
    try:
        # Создаем полный бэкап
        file_path = ExportService.export_full_database_backup(user_id)
        
        if file_path:
            filename = f"Полный_бэкап_БД_{context.bot_data.get('current_date', 'backup')}.xlsx"
            
            with open(file_path, 'rb') as file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file,
                    filename=filename,
                    caption="🗄️ Полная резервная копия БД"
                )
            
            # Очищаем временный файл
            ExportService.cleanup_temp_file(file_path)
            
            keyboard = [[InlineKeyboardButton("◀️ Назад в управление БД", callback_data="manage_db")]]
            await query.edit_message_text(
                "✅ Полный бэкап БД отправлен",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text("❌ Ошибка при создании бэкапа. Попробуйте позже.")
            
    except Exception as e:
        logger.error(f"Ошибка создания бэкапа БД для пользователя {user_id}: {e}")
        await query.edit_message_text("❌ Произошла ошибка при создании бэкапа.")

  
async def export_full_db_to_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт полной БД в Excel с форматированием (только для владельца)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    
    if user_id != OWNER_ID:
        await query.answer("⛔️ Эта команда доступна только создателю бота.", show_alert=True)
        return
    
    await query.edit_message_text("⏳ Начинаю полный экспорт. Это может занять до минуты...")
    
    try:
        # Сначала отправляем сырой бэкап
        raw_file_path = ExportService.export_full_database_backup(user_id)
        if raw_file_path:
            filename_raw = f"Полная_выгрузка_БД_raw_{context.bot_data.get('current_date', 'export')}.xlsx"
            with open(raw_file_path, 'rb') as file:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file,
                    filename=filename_raw,
                    caption="📊 Сырая выгрузка БД (все данные как есть)"
                )
            ExportService.cleanup_temp_file(raw_file_path)
        
        # Затем отправляем форматированный файл
        formatted_file_path = ExportService.export_formatted_database(user_id)
        if formatted_file_path:
            filename_formatted = f"Полная_выгрузка_БД_формат_{context.bot_data.get('current_date', 'export')}.xlsx"
            with open(formatted_file_path, 'rb') as file:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file,
                    filename=filename_formatted,
                    caption="📋 Форматированная выгрузка БД (читаемые названия)"
                )
            ExportService.cleanup_temp_file(formatted_file_path)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад в управление БД", callback_data="manage_db")]]
        await query.edit_message_text(
            "✅ Полный экспорт завершен. Отправлены 2 файла: сырой и форматированный.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка полного экспорта БД для пользователя {user_id}: {e}")
        await query.edit_message_text("❌ Произошла ошибка при формировании файлов.")


async def get_directories_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачивание шаблона справочников (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    
    # Проверяем права (только админы)
    if not user_role.get('isAdmin'):
        await query.edit_message_text("⛔️ У вас нет прав для работы со справочниками.")
        return
    
    await query.edit_message_text("⏳ Формирую шаблон справочников...")
    
    try:
        file_path = ExportService.generate_directories_template()
        
        if file_path:
            filename = f"Шаблон_справочников_{context.bot_data.get('current_date', 'template')}.xlsx"
            
            with open(file_path, 'rb') as file:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=file,
                    filename=filename,
                    caption=(
                        "📄 Шаблон справочников\n\n"
                        "Инструкция:\n"
                        "1. Отредактируйте данные в Excel\n"
                        "2. Отправьте файл обратно боту\n"
                        "3. Изменения будут применены автоматически"
                    )
                )
            
            # Очищаем временный файл
            ExportService.cleanup_temp_file(file_path)
            
            keyboard = [[InlineKeyboardButton("◀️ Назад к справочникам", callback_data="manage_directories")]]
            await query.edit_message_text(
                "✅ Шаблон справочников отправлен",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text("❌ Ошибка при создании шаблона. Попробуйте позже.")
            
    except Exception as e:
        logger.error(f"Ошибка создания шаблона справочников для пользователя {user_id}: {e}")
        await query.edit_message_text("❌ Произошла ошибка при создании шаблона.")


async def export_all_users_to_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт всех пользователей в Excel (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    
    # Проверяем права (только админы)
    if not user_role.get('isAdmin'):
        await query.edit_message_text("⛔️ У вас нет прав для экспорта пользователей.")
        return
    
    await query.edit_message_text("⏳ Формирую список всех пользователей...")
    
    try:
        from sqlalchemy import create_engine, text
        from config.settings import DATABASE_URL
        import pandas as pd
        import os
        from utils.constants import TEMP_DIR
        
        ExportService.create_temp_directory()
        
        current_date_str = context.bot_data.get('current_date', 'export')
        file_path = os.path.join(TEMP_DIR, f"all_users_{user_id}_{current_date_str}.xlsx")
        
        engine = create_engine(DATABASE_URL)
        
        # Собираем пользователей из всех таблиц ролей
        user_tables = {
            'Админы': 'SELECT user_id, first_name, last_name, username, phone_number, created_at FROM admins',
            'Менеджеры': '''
                SELECT m.user_id, m.first_name, m.last_name, m.username, m.phone_number, 
                       m.level as "Уровень", d.name as "Дисциплина", m.created_at 
                FROM managers m 
                LEFT JOIN disciplines d ON m.discipline = d.id
            ''',
            'Супервайзеры': '''
                SELECT s.user_id, s.first_name, s.last_name, s.username, s.phone_number,
                       d.name as "Дисциплина", s.created_at
                FROM supervisors s
                LEFT JOIN disciplines d ON s.discipline_id = d.id  
            ''',
            'Мастера': '''
                SELECT m.user_id, m.first_name, m.last_name, m.username, m.phone_number,
                       d.name as "Дисциплина", m.created_at
                FROM masters m
                LEFT JOIN disciplines d ON m.discipline_id = d.id
            ''',
            'Бригадиры': '''
                SELECT b.user_id, b.first_name, b.last_name, b.username, b.phone_number,
                       b.brigade_name as "Бригада", d.name as "Дисциплина", b.created_at
                FROM brigades b
                LEFT JOIN disciplines d ON b.discipline_id = d.id
            ''',
            'ПТО': '''
                SELECT p.user_id, p.first_name, p.last_name, p.username, p.phone_number,
                       d.name as "Дисциплина", p.created_at
                FROM pto p
                LEFT JOIN disciplines d ON p.discipline_id = d.id
            ''',
            'КИОК': '''
                SELECT k.user_id, k.first_name, k.last_name, k.username, k.phone_number,
                       k.kiok_name as "Имя КИОК", d.name as "Дисциплина", k.created_at
                FROM kiok k
                LEFT JOIN disciplines d ON k.discipline_id = d.id
            '''
        }
        
        with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
            with engine.connect() as connection:
                for sheet_name, query_text in user_tables.items():
                    try:
                        df = pd.read_sql_query(text(query_text), connection)
                        
                        if not df.empty:
                            # Переименовываем стандартные колонки
                            rename_map = {
                                'user_id': 'ID пользователя',
                                'first_name': 'Имя',
                                'last_name': 'Фамилия',
                                'username': 'Username',
                                'phone_number': 'Телефон',
                                'created_at': 'Дата регистрации'
                            }
                            df = df.rename(columns=rename_map)
                            
                            # Форматируем дату
                            if 'Дата регистрации' in df.columns:
                                df['Дата регистрации'] = pd.to_datetime(df['Дата регистрации'], errors='coerce')
                                if df['Дата регистрации'].dt.tz is not None:
                                    df['Дата регистрации'] = df['Дата регистрации'].dt.tz_localize(None)
                            
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            
                            # Настраиваем ширину колонок
                            worksheet = writer.sheets[sheet_name]
                            for i, col in enumerate(df.columns):
                                if not df[col].empty:
                                    max_len = df[col].astype(str).map(len).max()
                                else:
                                    max_len = 0
                                column_len = max(max_len, len(col)) + 2
                                worksheet.set_column(i, i, min(column_len, 30))
                        
                    except Exception as table_error:
                        logger.error(f"Ошибка экспорта таблицы {sheet_name}: {table_error}")
                        continue
        
        filename = f"Все_пользователи_{current_date_str}.xlsx"
        
        with open(file_path, 'rb') as file:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=file,
                filename=filename,
                caption="👥 Список всех пользователей системы"
            )
        
        # Очищаем временный файл
        ExportService.cleanup_temp_file(file_path)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад к управлению пользователями", callback_data="manage_users")]]
        await query.edit_message_text(
            "✅ Список пользователей отправлен",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Ошибка экспорта пользователей для {user_id}: {e}")
        await query.edit_message_text("❌ Произошла ошибка при экспорте пользователей.")

@auto_clean
async def handle_db_restore_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
   """Обрабатывает загруженный файл для восстановления БД (адаптировано из старого кода)"""
   
   user_id = str(update.effective_user.id)
   
   # Проверяем права (только владелец)
   if user_id != OWNER_ID:
       await update.message.reply_text("⛔️ Доступ к восстановлению БД имеет только владелец бота.")
       return
   
   # Проверяем тип файла
   excel_mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
   if not update.message.document or update.message.document.mime_type != excel_mime_type:
       await update.message.reply_text("❌ Пожалуйста, отправьте Excel файл (.xlsx)")
       return
   
   # FIXED: Проверяем что файл ожидается для восстановления БД
   if not context.user_data.get('awaiting_db_backup'):
       return  # Игнорируем файл если не ожидаем восстановление
   
   # Очищаем флаг ожидания
   context.user_data.pop('awaiting_db_backup', None)
   
   await update.message.reply_text("⏳ Начинаю восстановление БД... Это может занять несколько минут.")
   
   try:
       from services.import_service import ImportService
       from utils.constants import TEMP_DIR
       
       # Скачиваем файл
       file = await context.bot.get_file(update.message.document.file_id)
       file_path = os.path.join(TEMP_DIR, f"restore_{user_id}.xlsx")
       await file.download_to_drive(file_path)
       
       # Восстанавливаем БД через сервис
       result = ImportService.restore_full_database_from_excel(file_path)
       
       if result.get('success', False):
            restored_tables = result.get('restored_tables', [])
            restored_count = len(restored_tables)
    
            # FIXED: Извлекаем только названия таблиц
            table_names = [table_info['table'] for table_info in restored_tables]
    
            success_text = (
                f"✅ База данных успешно восстановлена!\n\n"
                f"Восстановлено таблиц: **{restored_count}**\n"
                f"Список: {', '.join(table_names)}"  # FIXED: передаем список строк
            )
    
            await update.message.reply_text(
                success_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")
                ]]),
           
            )
       else:
           error_msg = result.get('error', 'Неизвестная ошибка')
           await update.message.reply_text(f"❌ Ошибка восстановления: {error_msg}")
           
   except Exception as e:
       logger.error(f"Ошибка восстановления БД: {e}")
       await update.message.reply_text("❌ Произошла ошибка при восстановлении.")

   finally:
     # FIXED: Безопасное удаление временного файла для Windows
     if 'file_path' in locals() and os.path.exists(file_path):
         try:
             import gc
             import time
             gc.collect()  # Принудительная сборка мусора
             time.sleep(0.2)  # Задержка для освобождения файла
             os.remove(file_path)
             logger.info(f"Временный файл удален: {file_path}")
         except (PermissionError, OSError):
             # Windows может держать файл, оставляем его (не критично)
             logger.warning(f"Временный файл не удален (занят процессом): {file_path}")
         except Exception as e:
             logger.error(f"Ошибка удаления временного файла: {e}")

# === ПРОМЕЖУТОЧНЫЕ ОБРАБОТЧИКИ ===


async def handle_hr_date_quick_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрые кнопки для HR отчетов (сегодня/вчера)"""
    query = update.callback_query
    await query.answer()
    
    # Парсим callback: hr_report_[today/yesterday]_[discipline_id]
    parts = query.data.split('_')
    if len(parts) < 4:
        await query.edit_message_text("❌ Ошибка разбора данных.")
        return
    
    date_type = parts[2]  # today или yesterday
    discipline_id = parts[3]
    
    # Определяем дату
    if date_type == 'today':
        selected_date = date.today()
    else:  # yesterday
        selected_date = date.today() - timedelta(days=1)
    
    # Импортируем функцию из analytics
    from bot.handlers.analytics import show_hr_report_for_date
    await show_hr_report_for_date(update, context, discipline_id, selected_date)


async def handle_problem_brigades_quick_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрые кнопки для отчетов по проблемным бригадам"""
    query = update.callback_query
    await query.answer()
    
    # Определяем дату из callback
    if "today" in query.data:
        selected_date = date.today()
    elif "yesterday" in query.data:
        selected_date = date.today() - timedelta(days=1)
    else:
        await query.edit_message_text("❌ Ошибка определения даты.")
        return
    
    # Импортируем функцию из analytics
    from bot.handlers.analytics import generate_problem_brigades_report
    await generate_problem_brigades_report(update, context)

def register_export_handlers(application):
    """Регистрация обработчиков экспорта"""
    from telegram.ext import CallbackQueryHandler, MessageHandler, filters
    from datetime import date, timedelta
    
    # Основные функции экспорта
    application.add_handler(CallbackQueryHandler(export_reports_to_excel, pattern="^get_excel_report$"))
    application.add_handler(CallbackQueryHandler(download_db_backup, pattern="^db_backup_download$"))
    application.add_handler(CallbackQueryHandler(export_full_db_to_excel, pattern="^export_full_db$"))
    application.add_handler(CallbackQueryHandler(get_directories_template, pattern="^get_directories_template_button$"))
    application.add_handler(CallbackQueryHandler(export_all_users_to_excel, pattern="^export_all_users$"))
    
    # НОВЫЕ обработчики
    application.add_handler(MessageHandler(
        filters.Document.MimeType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") & 
        filters.User(user_id=int(OWNER_ID)),
        handle_db_restore_file
    ))
    
    # Быстрые кнопки для отчетов
    application.add_handler(CallbackQueryHandler(handle_hr_date_quick_buttons, pattern="^hr_report_(today|yesterday)_"))
    application.add_handler(CallbackQueryHandler(handle_problem_brigades_quick_buttons, pattern="^problem_brigades_by_date_(today|yesterday)$"))
    