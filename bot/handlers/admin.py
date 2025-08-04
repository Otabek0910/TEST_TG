# bot/handlers/admin.py

import logging
import os
from datetime import date
from typing import Dict, Any, List, Optional
import pandas as pd
from sqlalchemy import create_engine, text

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, CommandHandler
# Добавить после существующих импортов:
from telegram.ext import ConversationHandler
from utils.constants import AWAITING_NEW_DISCIPLINE, AWAITING_NEW_LEVEL, AWAITING_RESTORE_FILE, GETTING_HR_DATE, SELECTING_OVERVIEW_ACTION, AWAITING_OVERVIEW_DATE, GETTING_HR_DATE


from bot.middleware.security import check_user_role
from utils.chat_utils import auto_clean
from utils.localization import get_user_language, get_text
from config.settings import OWNER_ID, DATABASE_URL
from database.queries import db_query, db_execute
from services.user_management_service import UserManagementService

logger = logging.getLogger(__name__)

TEMP_DIR = 'temp_files'
os.makedirs(TEMP_DIR, exist_ok=True)


async def manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню управления (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = await get_user_language(user_id)

    # Проверяем права доступа
    if not (user_role.get('isAdmin') or user_role.get('isManager')):
        await query.edit_message_text("⛔️ У вас нет прав для управления системой.")
        return

    keyboard = [
        [InlineKeyboardButton("👥 Управление пользователями", callback_data="manage_users")],
        [InlineKeyboardButton("📂 Управление справочниками", callback_data="manage_directories")],
    ]

    # Управление отчетами (только для админов)
    if user_role.get('isAdmin'):
        keyboard.append([InlineKeyboardButton("🗂️ Управление отчетами", callback_data="admin_report_menu_start")])

    # Управление данными (только для владельца)
    if user_id == OWNER_ID:
        keyboard.append([InlineKeyboardButton("🗄️ Управление данными", callback_data="manage_db")])

    keyboard.append([InlineKeyboardButton("◀️ Назад в главное меню", callback_data="back_to_start")])

    await query.edit_message_text(
        text="⚙️ **Меню управления**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def manage_users_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления пользователями с подсчетом по ролям (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)

    # Проверяем права доступа
    if not (user_role.get('isAdmin') or user_role.get('isManager')):
        await query.edit_message_text("⛔️ У вас нет прав для управления пользователями.")
        return

    try:
        # Подсчитываем количество пользователей по ролям
        counts = {}
        
        # CHANGED: Адаптируем под новую схему с новыми ролями
        role_tables = {
            'admins': 'Администраторы',
            'managers': 'Менеджеры', 
            'supervisors': 'Супервайзеры',
            'masters': 'Мастера',
            'brigades': 'Бригадиры',
            'pto': 'ПТО',
            'kiok': 'КИОК'
        }
        
        for table_name, display_name in role_tables.items():
            try:
                result = db_query(f"SELECT COUNT(*) FROM {table_name}")
                counts[table_name] = result[0][0] if result else 0
            except Exception as e:
                logger.error(f"Ошибка подсчета пользователей в таблице {table_name}: {e}")
                counts[table_name] = 0
        
        # Формируем текст сводки
        summary_lines = [
            "📊 **Сводка по ролям:**",
            f"  ▪️ Администраторы: **{counts['admins']}**",
            f"  ▪️ Менеджеры: **{counts['managers']}**",
            f"  ▪️ Супервайзеры: **{counts['supervisors']}**",
            f"  ▪️ Мастера: **{counts['masters']}**",
            f"  ▪️ Бригадиры: **{counts['brigades']}**",
            f"  ▪️ ПТО: **{counts['pto']}**",
            f"  ▪️ КИОК: **{counts['kiok']}**",
            "",
            "Выберите роль для просмотра списка:"
        ]
        
        summary_text = "\n".join(summary_lines)

        # Формируем кнопки
        keyboard = [
            [InlineKeyboardButton("👑 Администраторы", callback_data="list_users_admins_1")],
            [InlineKeyboardButton("💼 Менеджеры", callback_data="list_users_managers_1")],
            [InlineKeyboardButton("👨‍🔧 Супервайзеры", callback_data="list_users_supervisors_1")],
            [InlineKeyboardButton("🔨 Мастера", callback_data="list_users_masters_1")],
            [InlineKeyboardButton("👷 Бригадиры", callback_data="list_users_brigades_1")],
            [InlineKeyboardButton("🛠️ ПТО", callback_data="list_users_pto_1")],
            [InlineKeyboardButton("✅ КИОК", callback_data="list_users_kiok_1")],
            [InlineKeyboardButton("📋 Экспорт всех пользователей", callback_data="export_all_users")],
            [InlineKeyboardButton("◀️ Назад в управление", callback_data="manage_menu")]
        ]
        
        await query.edit_message_text(
            text=summary_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )

    except Exception as e:
        logger.error(f"Ошибка в manage_users_menu: {e}")
        await query.edit_message_text("❌ Произошла ошибка при загрузке данных о пользователях.")


async def manage_db_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню управления базой данных (только для владельца)"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    
    # Проверяем права доступа (только владелец)
    if user_id != OWNER_ID:
        await query.edit_message_text("⛔️ Доступ к управлению данными имеет только владелец бота.")
        return

    keyboard = [
        [InlineKeyboardButton("📥 Скачать резервную копию БД", callback_data="db_backup_download")],
        [InlineKeyboardButton("📤 Полный экспорт БД (2 файла)", callback_data="export_full_db")],
        [InlineKeyboardButton("📋 Экспорт всех пользователей", callback_data="export_all_users")],
        [InlineKeyboardButton("🔄 Восстановление БД", callback_data="db_backup_upload_prompt")],
        [InlineKeyboardButton("◀️ Назад в управление", callback_data="manage_menu")],
    ]
    
    text = (
        "🗄️ **Управление данными**\n\n"
        "**ВНИМАНИЕ:** Операции с БД влияют на все данные системы.\n\n"
        "📥 **Резервная копия** - стандартный бэкап для восстановления\n"
        "📤 **Полный экспорт** - сырые + форматированные данные\n"
        "🔄 **Восстановление** - полная перезапись БД из файла"
    )
    
    await query.edit_message_text(
        text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.MARKDOWN
    )


async def manage_directories_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню для работы со справочниками"""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)

    # Проверяем права доступа
    if not user_role.get('isAdmin'):
        await query.edit_message_text("⛔️ У вас нет прав для управления справочниками.")
        return

    keyboard = [
        [InlineKeyboardButton("📄 Скачать шаблон (Excel)", callback_data="get_directories_template_button")],
        [InlineKeyboardButton("📊 Просмотр справочников", callback_data="view_directories_info")],
        [InlineKeyboardButton("◀️ Назад в управление", callback_data="manage_menu")]
    ]
    
    caption = (
        "📂 **Управление справочниками**\n\n"
        "**Инструкция:**\n"
        "1. **Скачайте шаблон** для просмотра текущих данных\n"
        "2. **Отредактируйте** файл (добавьте или измените строки)\n"
        "3. **Отправьте файл** обратно боту для применения изменений\n\n"
        "💡 Бот автоматически обработает загруженный Excel файл"
    )

    await query.edit_message_text(
        text=caption,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def view_directories_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о справочниках"""
    query = update.callback_query
    await query.answer()

    try:
        # Подсчитываем записи в справочниках
        disciplines_count = db_query("SELECT COUNT(*) FROM disciplines")[0][0]
        objects_count = db_query("SELECT COUNT(*) FROM construction_objects")[0][0]
        work_types_count = db_query("SELECT COUNT(*) FROM work_types")[0][0]
        
        # Показываем последние добавленные
        recent_disciplines = db_query("SELECT name FROM disciplines ORDER BY created_at DESC LIMIT 3")
        recent_objects = db_query("SELECT name FROM construction_objects ORDER BY created_at DESC LIMIT 3")
        
        info_lines = [
            "📊 **Состояние справочников:**",
            f"  ▪️ Дисциплины: **{disciplines_count}** записей",
            f"  ▪️ Корпуса: **{objects_count}** записей", 
            f"  ▪️ Виды работ: **{work_types_count}** записей",
            ""
        ]
        
        if recent_disciplines:
            info_lines.append("🆕 **Последние дисциплины:**")
            for disc in recent_disciplines:
                info_lines.append(f"  • {disc[0]}")
            info_lines.append("")
        
        if recent_objects:
            info_lines.append("🆕 **Последние корпуса:**")
            for obj in recent_objects:
                info_lines.append(f"  • {obj[0]}")
        
        info_text = "\n".join(info_lines)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад к справочникам", callback_data="manage_directories")]]
        
        await query.edit_message_text(
            text=info_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о справочниках: {e}")
        await query.edit_message_text("❌ Ошибка получения информации о справочниках.")


async def show_user_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню редактирования конкретного пользователя (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()

    # Парсим данные из callback
    parts = query.data.split('_')
    if len(parts) < 4:
        await query.edit_message_text("❌ Ошибка разбора данных пользователя.")
        return
        
    role = parts[2]  # edit_user_[role]_[user_id]
    user_id_to_edit = parts[3]

    viewer_id = str(query.from_user.id)
    viewer_role = check_user_role(viewer_id)
    
    # Проверяем права доступа
    if not (viewer_role.get('isAdmin') or viewer_role.get('isManager')):
        await query.edit_message_text("⛔️ У вас нет прав для редактирования пользователей.")
        return
    
    try:
        # Получаем данные пользователя
        user_data = db_query(f"SELECT first_name, last_name FROM {role} WHERE user_id = %s", (user_id_to_edit,))
        
        if not user_data:
            await query.edit_message_text("❌ Пользователь не найден.")
            return
            
        full_name = f"{user_data[0][0]} {user_data[0][1]}" if user_data[0][0] and user_data[0][1] else user_id_to_edit

        message_text = f"👤 **Редактирование: {full_name}**\n`{user_id_to_edit}`\n\nВыберите действие:"

        keyboard_buttons = []
        
        # Опции редактирования в зависимости от роли
        if role == 'managers':
            keyboard_buttons.append([InlineKeyboardButton("📊 Изменить уровень", callback_data=f"change_level_{user_id_to_edit}")])
            keyboard_buttons.append([InlineKeyboardButton("🏭 Изменить дисциплину", callback_data=f"change_discipline_{role}_{user_id_to_edit}")])
        elif role in ['pto', 'kiok', 'supervisors', 'masters']:
            keyboard_buttons.append([InlineKeyboardButton("🏭 Изменить дисциплину", callback_data=f"change_discipline_{role}_{user_id_to_edit}")])
        elif role == 'brigades':
            keyboard_buttons.append([InlineKeyboardButton("🏭 Изменить дисциплину", callback_data=f"change_discipline_{role}_{user_id_to_edit}")])
            
            # Сброс табеля для бригадиров (только для админов, менеджеров 2 уровня и ПТО)
            if viewer_role.get('isAdmin') or viewer_role.get('managerLevel') == 2 or viewer_role.get('isPto'):
                keyboard_buttons.append([InlineKeyboardButton("🔄 Сбросить табель", callback_data=f"reset_roster_{user_id_to_edit}")])

        # Удаление пользователя (только для админов, исключая себя и владельца)
        if (viewer_role.get('isAdmin') and 
            viewer_id != user_id_to_edit and 
            user_id_to_edit != OWNER_ID):
            keyboard_buttons.append([InlineKeyboardButton("🗑️ Удалить пользователя", callback_data=f"delete_user_{role}_{user_id_to_edit}")])
        
        # Кнопка "Назад"
        keyboard_buttons.append([InlineKeyboardButton("◀️ Назад к списку", callback_data=f"list_users_{role}_1")])

        await query.edit_message_text(
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard_buttons),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка в show_user_edit_menu: {e}")
        await query.edit_message_text("❌ Ошибка при загрузке данных пользователя.")


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает список пользователей с пагинацией"""
    query = update.callback_query
    await query.answer()
    
    # Парсим данные из callback_data: list_users_[роль]_[страница]
    parts = query.data.split('_')
    if len(parts) < 4:
        await query.edit_message_text("❌ Неверный формат данных для списка пользователей.")
        return
    
    role = parts[2]
    page = int(parts[3])
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    
    # Проверяем права доступа
    if not (user_role.get('isAdmin') or user_role.get('isManager')):
        await query.edit_message_text("⛔️ У вас нет прав для просмотра списков пользователей.")
        return
    
    await UserManagementService.list_users_with_pagination(query, role, page)


async def download_db_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Формирует и отправляет полный бэкап БД в Excel"""
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != OWNER_ID:
        await query.edit_message_text("⛔️ Доступ к бэкапу БД имеет только владелец бота.")
        return

    await query.edit_message_text("⏳ Формирую полную резервную копию... Это может занять некоторое время.")
    
    file_path = os.path.join(TEMP_DIR, f"full_backup_{date.today()}.xlsx")
    
    try:
        # Список таблиц для бэкапа
        table_names = [
            'disciplines', 'construction_objects', 'work_types', 'admins', 'managers', 
            'supervisors', 'masters', 'brigades', 'pto', 'kiok', 'reports', 'topic_mappings', 
            'personnel_roles', 'daily_rosters', 'daily_roster_details'
        ]
        
        engine = create_engine(DATABASE_URL)
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            with engine.connect() as connection:
                for table_name in table_names:
                    # Проверяем существование таблицы
                    query_check_table = text("SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename  = :table_name)")
                    if connection.execute(query_check_table, {'table_name': table_name}).scalar():
                        df = pd.read_sql_query(text(f"SELECT * FROM {table_name}"), connection)
                        
                        # Обработка специфичных полей с датами/временем
                        if table_name == 'reports':
                            timezone_cols = ['timestamp', 'kiok_approval_timestamp']
                            for col in timezone_cols:
                                if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
                                    if df[col].dt.tz is not None:
                                        df[col] = df[col].dt.tz_localize(None)
                        
                        df.to_excel(writer, sheet_name=table_name, index=False)
                    else:
                        logger.warning(f"Таблица {table_name} не найдена в БД, пропущена в бэкапе.")
        
        # Отправляем файл владельцу
        await context.bot.send_document(
            chat_id=OWNER_ID,
            document=open(file_path, 'rb'),
            caption="✅ Полная резервная копия базы данных."
        )
        await query.delete_message()
    except Exception as e:
        logger.error(f"Ошибка при создании бэкапа: {e}")
        await query.edit_message_text(f"❌ Произошла ошибка при создании резервной копии: {str(e)}")
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)


async def export_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Формирует и отправляет список всех пользователей в Excel"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    if user_id != OWNER_ID and not (check_user_role(user_id).get('isAdmin')):
        await query.edit_message_text("⛔️ У вас нет прав для экспорта списка пользователей.")
        return
    
    await query.edit_message_text("👥 Собираю всех пользователей в один список...")
    file_path = os.path.join(TEMP_DIR, f"all_users_{date.today()}.xlsx")

    try:
        engine = create_engine(DATABASE_URL)
        all_users_df = pd.DataFrame()
        roles = ['admins', 'managers', 'supervisors', 'masters', 'brigades', 'pto', 'kiok']
        
        with engine.connect() as connection:
            for role in roles:
                # Проверяем существование таблицы
                query_check_table = text("SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = :table_name)")
                if connection.execute(query_check_table, {'table_name': role}).scalar():
                    # Получаем общие поля для всех таблиц
                    df = pd.read_sql_query(text(f"SELECT user_id, first_name, last_name, username, phone_number FROM {role}"), connection)
                    df['role'] = role
                    all_users_df = pd.concat([all_users_df, df], ignore_index=True)

        all_users_df.to_excel(file_path, index=False)
        
        # Отправляем файл пользователю
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=open(file_path, 'rb'),
            caption="✅ Полный список зарегистрированных пользователей."
        )
        await query.delete_message()
    except Exception as e:
        logger.error(f"Ошибка при экспорте пользователей: {e}")
        await query.edit_message_text(f"❌ Произошла ошибка при экспорте пользователей: {str(e)}")
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)


async def db_backup_upload_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает инструкцию для загрузки бэкапа БД"""
    query = update.callback_query
    await query.answer()
    
    if str(query.from_user.id) != OWNER_ID:
        await query.edit_message_text("⛔️ Доступ к восстановлению БД имеет только владелец бота.")
        return
    
    text = (
        "🔄 **Восстановление базы данных**\n\n"
        "⚠️ **ВНИМАНИЕ! ЭТО ОПАСНАЯ ОПЕРАЦИЯ!**\n"
        "Восстановление из резервной копии полностью перезапишет текущие данные.\n\n"
        "**Инструкция:**\n"
        "1. Отправьте Excel-файл с резервной копией\n"
        "2. Дождитесь завершения восстановления\n\n"
        "❗ **Все текущие данные будут удалены и заменены**"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data="manage_db")]]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Устанавливаем состояние для обработки загружаемого файла
    context.user_data['awaiting_db_backup'] = True


def register_admin_handlers(application):
    """Регистрация админских обработчиков"""
    from telegram.ext import CallbackQueryHandler
    
    # Основные меню управления
    application.add_handler(CallbackQueryHandler(manage_menu, pattern="^manage_menu$"))
    application.add_handler(CallbackQueryHandler(manage_users_menu, pattern="^manage_users$"))
    application.add_handler(CallbackQueryHandler(manage_db_menu, pattern="^manage_db$"))
    application.add_handler(CallbackQueryHandler(manage_directories_menu, pattern="^manage_directories$"))
    
    # Информация о справочниках
    application.add_handler(CallbackQueryHandler(view_directories_info, pattern="^view_directories_info$"))
    
    # Редактирование пользователей
    application.add_handler(CallbackQueryHandler(show_user_edit_menu, pattern="^edit_user_"))
     
    # Экспорт и бэкап
    application.add_handler(CallbackQueryHandler(download_db_backup, pattern="^db_backup_download$"))
    application.add_handler(CallbackQueryHandler(export_all_users, pattern="^export_all_users$"))
    application.add_handler(CallbackQueryHandler(db_backup_upload_prompt, pattern="^db_backup_upload_prompt$"))
    
    
    # TODO: Добавить остальные обработчики:
    # - list_users (показ списков пользователей с пагинацией)
    # - delete_user (удаление пользователей)
    # - change_discipline (смена дисциплины)
    # - change_level (смена уровня менеджера)
    # - reset_roster (сброс табеля)
    
    logger.info("✅ Admin handlers зарегистрированы")


async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаляет пользователя и уведомляет его об этом"""
    query = update.callback_query
    await query.answer("Удаляю...", show_alert=False)
    
    # Парсим данные из callback_data: delete_user_[роль]_[user_id]
    parts = query.data.split('_')
    if len(parts) < 4:
        await query.edit_message_text("❌ Неверный формат данных для удаления пользователя.")
        return
    
    role_to_delete = parts[2]
    user_id_to_delete = parts[3]
    
    admin_id = str(query.from_user.id)
    admin_role = check_user_role(admin_id)
    
    # Проверяем права доступа (только админ)
    if not admin_role.get('isAdmin'):
        await query.edit_message_text("⛔️ У вас нет прав для удаления пользователей.")
        return
    
    # Нельзя удалить самого себя или владельца
    if admin_id == user_id_to_delete or user_id_to_delete == OWNER_ID:
        await query.edit_message_text("⛔️ Невозможно удалить этого пользователя.")
        return
    
    # Удаляем пользователя
    success = await UserManagementService.delete_user(role_to_delete, user_id_to_delete)
    
    if success:
        # Пытаемся уведомить пользователя
        try:
            if int(user_id_to_delete) in context._application.user_data:
                context._application.user_data[int(user_id_to_delete)].clear()
                logger.info(f"Состояние для пользователя {user_id_to_delete} было сброшено.")
            
            greeting_text = "⚠️ Ваша роль была удалена администратором. Для дальнейшей работы пройдите авторизацию заново."
            
            # Отправляем пользователю сообщение
            await context.bot.send_message(
                chat_id=int(user_id_to_delete),
                text=greeting_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔑 Авторизоваться", callback_data="start_auth")
                ]])
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id_to_delete} об удалении: {e}")
        
        # Показываем админу подтверждение
        keyboard = [[InlineKeyboardButton("◀️ Назад к списку", callback_data=f"list_users_{role_to_delete}_1")]]
        await query.edit_message_text(
            text=f"✅ Пользователь `{user_id_to_delete}` успешно удален.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # В случае ошибки
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_user_{role_to_delete}_{user_id_to_delete}")]]
        await query.edit_message_text(
            text="❌ Произошла ошибка при удалении пользователя.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def confirm_reset_roster(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запрашивает подтверждение на сброс табеля"""
    query = update.callback_query
    await query.answer()
    
    # Парсим данные из callback_data: reset_roster_[user_id]
    parts = query.data.split('_')
    if len(parts) < 3:
        await query.edit_message_text("❌ Неверный формат данных для сброса табеля.")
        return
    
    user_id_to_reset = parts[2]
    
    admin_id = str(query.from_user.id)
    admin_role = check_user_role(admin_id)
    
    # Проверяем права доступа
    if not (admin_role.get('isAdmin') or admin_role.get('managerLevel') == 2 or admin_role.get('isPto')):
        await query.edit_message_text("⛔️ У вас нет прав для сброса табеля.")
        return
    
    # Получаем информацию о пользователе
    user_data = db_query("SELECT first_name, last_name FROM brigades WHERE user_id = %s", (user_id_to_reset,))
    if not user_data:
        await query.edit_message_text("❌ Пользователь не найден или не является бригадиром.")
        return
    
    first_name = user_data[0][0] or ""
    last_name = user_data[0][1] or ""
    full_name = f"{first_name} {last_name}".strip() or user_id_to_reset
    
    # Запрашиваем подтверждение
    text = (
        f"‼️ **Вы уверены, что хотите сбросить сегодняшний табель для бригадира {full_name}?**\n\n"
        f"Он сможет подать его заново. Это действие необратимо."
    )
    keyboard = [
        [InlineKeyboardButton("✅ Да, сбросить", callback_data=f"execute_reset_roster_{user_id_to_reset}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"edit_user_brigades_{user_id_to_reset}")]
    ]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def execute_reset_roster(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выполняет сброс табеля для бригадира"""
    query = update.callback_query
    await query.answer("Сбрасываю табель...")
    
    # Парсим данные из callback_data: execute_reset_roster_[user_id]
    parts = query.data.split('_')
    if len(parts) < 4:
        await query.edit_message_text("❌ Неверный формат данных для сброса табеля.")
        return
    
    user_id_to_reset = parts[3]
    
    admin_id = str(query.from_user.id)
    admin_role = check_user_role(admin_id)
    
    # Проверяем права доступа
    if not (admin_role.get('isAdmin') or admin_role.get('managerLevel') == 2 or admin_role.get('isPto')):
        await query.edit_message_text("⛔️ У вас нет прав для сброса табеля.")
        return
    
    # Сбрасываем табель
    success = await UserManagementService.reset_roster(user_id_to_reset)
    
    if success:
        # Уведомляем пользователя
        try:
            greeting_text = "⚠️ Администратор сбросил ваш сегодняшний табель. Пожалуйста, подайте его заново."
            
            # Отправляем пользователю сообщение
            await context.bot.send_message(
                chat_id=int(user_id_to_reset),
                text=greeting_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📋 Подать табель", callback_data="submit_roster")
                ]])
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id_to_reset} о сбросе табеля: {e}")
        
        # Показываем админу подтверждение
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_user_brigades_{user_id_to_reset}")]]
        await query.edit_message_text(
            text="✅ Табель на сегодня успешно сброшен.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # В случае ошибки
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_user_brigades_{user_id_to_reset}")]]
        await query.edit_message_text(
            text="❌ Произошла ошибка при сбросе табеля.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_discipline_change_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает меню для смены дисциплины пользователя"""
    query = update.callback_query
    await query.answer()
    
    # Парсим данные: change_discipline_[role]_[user_id]
    parts = query.data.split('_')
    if len(parts) < 4:
        await query.edit_message_text("❌ Ошибка разбора данных.")
        return ConversationHandler.END
    
    role = parts[2]
    user_id_to_edit = parts[3]
    
    # Сохраняем в context для следующего шага
    context.user_data['edit_user_role'] = role
    context.user_data['edit_user_id'] = user_id_to_edit
    
    # Получаем список дисциплин
    disciplines = db_query("SELECT id, name FROM disciplines ORDER BY name")
    if not disciplines:
        await query.edit_message_text("❌ Дисциплины не найдены.")
        return ConversationHandler.END
    
    keyboard_buttons = []
    for disc_id, disc_name in disciplines:
        keyboard_buttons.append([InlineKeyboardButton(
            disc_name, 
            callback_data=f"set_new_discipline_{disc_id}"
        )])
    
    keyboard_buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_admin_op")])
    
    await query.edit_message_text(
        f"🏭 **Выберите новую дисциплину для пользователя:**",
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return AWAITING_NEW_DISCIPLINE


async def handle_discipline_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает смену дисциплины"""
    query = update.callback_query
    await query.answer("Изменяю дисциплину...")
    
    # Получаем новую дисциплину из callback
    new_discipline_id = query.data.replace('set_new_discipline_', '')
    role = context.user_data.get('edit_user_role')
    user_id_to_edit = context.user_data.get('edit_user_id')
    
    if not role or not user_id_to_edit:
        await query.edit_message_text("❌ Ошибка: данные пользователя потеряны.")
        return ConversationHandler.END
    
    # Обновляем дисциплину в БД
    success = db_execute(
        f"UPDATE {role} SET discipline_id = %s WHERE user_id = %s",
        (new_discipline_id, user_id_to_edit)
    )
    
    if success:
        # Получаем название дисциплины для отображения
        disc_name_raw = db_query("SELECT name FROM disciplines WHERE id = %s", (new_discipline_id,))
        disc_name = disc_name_raw[0][0] if disc_name_raw else "Неизвестно"
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=int(user_id_to_edit),
                text=f"⚙️ Администратор изменил вашу дисциплину на «{disc_name}».",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")
                ]])
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id_to_edit}: {e}")
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_user_{role}_{user_id_to_edit}")]]
        await query.edit_message_text(
            f"✅ Дисциплина изменена на «{disc_name}».",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_user_{role}_{user_id_to_edit}")]]
        await query.edit_message_text(
            "❌ Ошибка при изменении дисциплины.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    context.user_data.clear()
    return ConversationHandler.END

# 2. СМЕНА УРОВНЯ МЕНЕДЖЕРА

async def show_level_change_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показывает меню для смены уровня менеджера"""
    query = update.callback_query
    await query.answer()
    
    # Парсим данные: change_level_[user_id]
    user_id_to_edit = query.data.replace('change_level_', '')
    context.user_data['edit_user_id'] = user_id_to_edit
    
    keyboard = [
        [InlineKeyboardButton("Уровень 1 (все дисциплины)", callback_data="set_new_level_1")],
        [InlineKeyboardButton("Уровень 2 (одна дисциплина)", callback_data="set_new_level_2")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_admin_op")]
    ]
    
    await query.edit_message_text(
        "📊 **Выберите новый уровень для менеджера:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return AWAITING_NEW_LEVEL

  
async def handle_level_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает смену уровня менеджера"""
    query = update.callback_query
    await query.answer("Изменяю уровень...")
    
    new_level = int(query.data.replace('set_new_level_', ''))
    user_id_to_edit = context.user_data.get('edit_user_id')
    
    if not user_id_to_edit:
        await query.edit_message_text("❌ Ошибка: данные пользователя потеряны.")
        return ConversationHandler.END
    
    # Если уровень 1, убираем привязку к дисциплине
    if new_level == 1:
        success = db_execute(
            "UPDATE managers SET level = %s, discipline = NULL WHERE user_id = %s",
            (new_level, user_id_to_edit)
        )
        
        if success:
            try:
                await context.bot.send_message(
                    chat_id=int(user_id_to_edit),
                    text="⚙️ Администратор присвоил вам Уровень 1. Теперь у вас доступ ко всем дисциплинам.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")
                    ]])
                )
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователя {user_id_to_edit}: {e}")
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_user_managers_{user_id_to_edit}")]]
            await query.edit_message_text(
                "✅ Уровень изменен на 1 (доступ ко всем дисциплинам).",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            context.user_data.clear()
            return ConversationHandler.END
    
    # Если уровень 2, нужно выбрать дисциплину
    else:
        context.user_data['new_level'] = new_level
        
        # Показываем список дисциплин
        disciplines = db_query("SELECT id, name FROM disciplines ORDER BY name")
        if not disciplines:
            await query.edit_message_text("❌ Дисциплины не найдены.")
            return ConversationHandler.END
        
        keyboard_buttons = []
        for disc_id, disc_name in disciplines:
            keyboard_buttons.append([InlineKeyboardButton(
                disc_name, 
                callback_data=f"set_level2_discipline_{disc_id}"
            )])
        
        keyboard_buttons.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_admin_op")])
        
        await query.edit_message_text(
            f"🏭 **Выберите дисциплину для Уровня 2:**",
            reply_markup=InlineKeyboardMarkup(keyboard_buttons),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return AWAITING_NEW_DISCIPLINE


async def handle_level2_discipline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает назначение дисциплины для уровня 2"""
    query = update.callback_query
    await query.answer("Сохраняю изменения...")
    
    discipline_id = query.data.replace('set_level2_discipline_', '')
    user_id_to_edit = context.user_data.get('edit_user_id')
    new_level = context.user_data.get('new_level')
    
    # Обновляем уровень и дисциплину
    success = db_execute(
        "UPDATE managers SET level = %s, discipline = %s WHERE user_id = %s",
        (new_level, discipline_id, user_id_to_edit)
    )
    
    if success:
        # Получаем название дисциплины
        disc_name_raw = db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,))
        disc_name = disc_name_raw[0][0] if disc_name_raw else "Неизвестно"
        
        try:
            await context.bot.send_message(
                chat_id=int(user_id_to_edit),
                text=f"⚙️ Администратор присвоил вам Уровень 2 и назначил дисциплину «{disc_name}».",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")
                ]])
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id_to_edit}: {e}")
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_user_managers_{user_id_to_edit}")]]
        await query.edit_message_text(
            f"✅ Присвоен Уровень 2 с дисциплиной «{disc_name}».",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"edit_user_managers_{user_id_to_edit}")]]
        await query.edit_message_text(
            "❌ Ошибка при сохранении изменений.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    context.user_data.clear()
    return ConversationHandler.END

# 3. ВОССТАНОВЛЕНИЕ БД

async def handle_db_restore_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает загруженный файл для восстановления БД"""
    
    user_id = str(update.effective_user.id)
    
    # Проверяем права (только владелец)
    if user_id != OWNER_ID:
        await update.message.reply_text("⛔️ Доступ к восстановлению БД имеет только владелец бота.")
        return ConversationHandler.END
    
    # Проверяем тип файла
    excel_mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if not update.message.document or update.message.document.mime_type != excel_mime_type:
        await update.message.reply_text("❌ Пожалуйста, отправьте Excel файл (.xlsx)")
        return AWAITING_RESTORE_FILE
    
    await update.message.reply_text("⏳ Начинаю восстановление БД... Это может занять несколько минут.")
    
    try:
        from services.import_service import ImportService
        
        # Скачиваем файл
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = os.path.join(TEMP_DIR, f"restore_{user_id}.xlsx")
        await file.download_to_drive(file_path)
        
        # Восстанавливаем БД
        success = ImportService.restore_database_from_excel(file_path)
        
        if success:
            await update.message.reply_text(
                "✅ База данных успешно восстановлена из резервной копии!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")
                ]])
            )
        else:
            await update.message.reply_text("❌ Ошибка при восстановлении БД. Проверьте файл.")
            
    except Exception as e:
        logger.error(f"Ошибка восстановления БД: {e}")
        await update.message.reply_text("❌ Произошла ошибка при восстановлении.")
    finally:
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)
    
    return ConversationHandler.END

# 4. ОТМЕНА ОПЕРАЦИЙ

async def cancel_admin_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет админскую операцию"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("❌ Операция отменена.")
    context.user_data.clear()
    return ConversationHandler.END

# === CONVERSATIONHANDLER'Ы ===

def create_admin_management_conversation():
    """Создает ConversationHandler для управления пользователями"""
    from telegram.ext import ConversationHandler, CallbackQueryHandler
    from utils.constants import AWAITING_NEW_DISCIPLINE, AWAITING_NEW_LEVEL
    
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_discipline_change_menu, pattern="^change_discipline_"),
            CallbackQueryHandler(show_level_change_menu, pattern="^change_level_"),
        ],
        states={
            AWAITING_NEW_DISCIPLINE: [
                CallbackQueryHandler(handle_discipline_change, pattern="^set_new_discipline_"),
                CallbackQueryHandler(handle_level2_discipline, pattern="^set_level2_discipline_"),
            ],
            AWAITING_NEW_LEVEL: [
                CallbackQueryHandler(handle_level_change, pattern="^set_new_level_"),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_operation, pattern="^cancel_admin_op$"),
        ],
        per_user=True,
       
        allow_reentry=True
    )

def create_db_restore_conversation():
    """Создает ConversationHandler для восстановления БД"""
    from telegram.ext import ConversationHandler, MessageHandler, filters
    from utils.constants import AWAITING_RESTORE_FILE
    
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(db_backup_upload_prompt, pattern="^db_backup_upload_prompt$")
        ],
        states={
            AWAITING_RESTORE_FILE: [
                MessageHandler(
                    filters.Document.MimeType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"), 
                    handle_db_restore_file
                )
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_operation, pattern="^cancel_admin_op$"),
        ],
        per_user=True,
        
        allow_reentry=True
    )

def create_hr_date_conversation():
    """Создает ConversationHandler для HR отчетов с выбором даты"""
    from telegram.ext import ConversationHandler, MessageHandler, filters, CallbackQueryHandler
    from utils.constants import GETTING_HR_DATE
    
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(show_hr_menu, pattern="^hr_date_select_"),
        ],
        states={
            GETTING_HR_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_hr_date)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_operation, pattern="^cancel_admin_op$"),
        ],
        per_user=True,
        allow_reentry=True
    )

async def show_hr_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню HR отчетов"""
    # Временная заглушка - будет реализовано в analytics
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🚧 HR отчеты в разработке")

async def process_hr_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает дату для HR отчета"""
    # Временная заглушка
    await update.message.reply_text("🚧 Обработка дат в разработке")
    return ConversationHandler.END


def register_admin_handlers(application):
    """Регистрация админских обработчиков"""
    
    # Основные меню управления
    application.add_handler(CallbackQueryHandler(manage_menu, pattern="^manage_menu$"))
    application.add_handler(CallbackQueryHandler(manage_users_menu, pattern="^manage_users$"))
    application.add_handler(CallbackQueryHandler(manage_db_menu, pattern="^manage_db$"))
    application.add_handler(CallbackQueryHandler(manage_directories_menu, pattern="^manage_directories$"))
    
    # Информация о справочниках
    application.add_handler(CallbackQueryHandler(view_directories_info, pattern="^view_directories_info$"))
    
    # Списки пользователей
    application.add_handler(CallbackQueryHandler(list_users, pattern="^list_users_"))
    
    # Редактирование пользователей
    application.add_handler(CallbackQueryHandler(show_user_edit_menu, pattern="^edit_user_"))
    application.add_handler(CallbackQueryHandler(delete_user, pattern="^delete_user_"))
    
    # Сброс табеля
    application.add_handler(CallbackQueryHandler(confirm_reset_roster, pattern="^reset_roster_"))
    application.add_handler(CallbackQueryHandler(execute_reset_roster, pattern="^execute_reset_roster_"))
    
    # Экспорт и бэкап
    application.add_handler(CallbackQueryHandler(download_db_backup, pattern="^db_backup_download$"))
    application.add_handler(CallbackQueryHandler(export_all_users, pattern="^export_all_users$"))
    
    logger.info("✅ Admin handlers зарегистрированы")
