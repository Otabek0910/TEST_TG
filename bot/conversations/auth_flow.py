"""
ConversationHandler для процесса авторизации
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import ConversationHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

from utils.constants import SELECTING_ROLE, GETTING_NAME, GETTING_CONTACT, SELECTING_MANAGER_LEVEL, SELECTING_DISCIPLINE
from utils.localization import get_text, get_user_language
from utils.chat_utils import clean_chat, track_message
from database.queries import db_query
from services.admin_service import AdminService

logger = logging.getLogger(__name__)

async def start_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало процесса авторизации"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_language(str(update.effective_user.id))  # ASYNC
    
    keyboard = [
        [InlineKeyboardButton("👨‍🔧 Супервайзер", callback_data="auth_supervisor")],
        [InlineKeyboardButton("🔨 Мастер", callback_data="auth_master")],
        [InlineKeyboardButton("👷 Бригадир", callback_data="auth_foreman")],
        [InlineKeyboardButton("📊 КИОК", callback_data="auth_kiok")],
        [InlineKeyboardButton("🏭 ПТО", callback_data="auth_pto")],
        [InlineKeyboardButton("👨‍💼 Менеджер", callback_data="auth_manager")],
        [InlineKeyboardButton(get_text('back_button', lang), callback_data="cancel_auth")]
    ]
    
    await query.edit_message_text(
        text=get_text('auth_prompt_role', lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    return SELECTING_ROLE

async def select_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора роли"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_language(str(update.effective_user.id))  # ASYNC
    
    context.user_data['selected_role'] = query.data.replace('auth_', '')
    
    await query.edit_message_text(
        text=get_text('auth_prompt_name', lang),
        parse_mode=ParseMode.HTML
    )
    return GETTING_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение ФИО"""
    lang = await get_user_language(str(update.effective_user.id))  # ASYNC
    
    await clean_chat(context, update.effective_chat.id)
    await update.message.delete()

    user_input = update.message.text.strip()
    if ' ' not in user_input or len(user_input.split()) < 2:
        sent_message = await context.bot.send_message(
            update.effective_chat.id, 
            get_text('auth_error_name', lang),
            parse_mode=ParseMode.HTML
        )
        await track_message(context, sent_message)
        return GETTING_NAME
    
    parts = user_input.split(' ', 1)
    context.user_data.update({'first_name': parts[0], 'last_name': parts[1]})
    
    reply_markup = ReplyKeyboardMarkup(
        [[KeyboardButton(text=get_text('auth_contact_button', lang), request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    
    sent_message = await context.bot.send_message(
        update.effective_chat.id, 
        get_text('auth_prompt_contact', lang), 
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    await track_message(context, sent_message)
    return GETTING_CONTACT

async def get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:  # FIXED: return int
    """Получение контакта"""
    await clean_chat(context, update.effective_chat.id)
    await update.message.delete()
    
    temp_msg = await context.bot.send_message(update.effective_chat.id, "...", reply_markup=ReplyKeyboardRemove())
    await temp_msg.delete()

    if update.message.contact:
        context.user_data['phone_number'] = update.message.contact.phone_number

    role = context.user_data.get('selected_role')
    if role == 'manager':
        return await handle_manager_level_entry(update, context)
    else:
        return await show_disciplines_selection_entry(update, context)

async def handle_manager_level_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point для выбора уровня менеджера"""
    lang = await get_user_language(str(update.effective_user.id))  # ASYNC
    
    keyboard = [
        [InlineKeyboardButton(get_text('auth_manager_level1', lang), callback_data="level_1")],
        [InlineKeyboardButton(get_text('auth_manager_level2', lang), callback_data="level_2")]
    ]
    
    await context.bot.send_message(
        update.effective_chat.id, 
        get_text('auth_prompt_manager_level', lang), 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )
    return SELECTING_MANAGER_LEVEL

async def handle_manager_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора уровня менеджера"""
    query = update.callback_query
    await query.answer()
    
    level = int(query.data.replace('level_', ''))
    context.user_data['manager_level'] = level
    
    if level == 1:
        return await finalize_registration(update, context)
    else:
        return await show_disciplines_selection(update, context)

async def show_disciplines_selection_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point для выбора дисциплины"""
    lang = await get_user_language(str(update.effective_user.id))  # ASYNC
    disciplines = await db_query("SELECT id, name FROM disciplines ORDER BY name")  # ASYNC
    
    if not disciplines:
        await context.bot.send_message(update.effective_chat.id, "❌ Ошибка: дисциплины не найдены в системе.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(name, callback_data=f"disc_{disc_id}")] for disc_id, name in disciplines]
    
    role_key = context.user_data.get('selected_role', '')
    role_map_loc = {
        'supervisor': 'супервайзера', 'master': 'мастера', 'manager': 'менеджера',
        'foreman': 'бригадира', 'kiok': 'КИОК', 'pto': 'ПТО'
    }
    role_for_text = role_map_loc.get(role_key, role_key)
    
    text_template = get_text('auth_prompt_discipline', lang)
    text = text_template.format(role=role_for_text)

    await context.bot.send_message(update.effective_chat.id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return SELECTING_DISCIPLINE

async def show_disciplines_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback для выбора дисциплины"""
    query = update.callback_query
    await query.answer()
    
    lang = await get_user_language(str(update.effective_user.id))  # ASYNC
    disciplines = await db_query("SELECT id, name FROM disciplines ORDER BY name")  # ASYNC
    
    if not disciplines:
        await query.edit_message_text("❌ Ошибка: дисциплины не найдены в системе.")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(name, callback_data=f"disc_{disc_id}")] for disc_id, name in disciplines]
    
    role_key = context.user_data.get('selected_role', '')
    role_map_loc = {
        'supervisor': 'супервайзера', 'master': 'мастера', 'manager': 'менеджера',
        'foreman': 'бригадира', 'kiok': 'КИОК', 'pto': 'ПТО'
    }
    role_for_text = role_map_loc.get(role_key, role_key)
    
    text_template = get_text('auth_prompt_discipline', lang)
    text = text_template.format(role=role_for_text)

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return SELECTING_DISCIPLINE

async def handle_discipline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора дисциплины"""
    query = update.callback_query
    await query.answer()
    context.user_data['discipline_id'] = query.data.replace('disc_', '')
    return await finalize_registration(update, context)

async def finalize_registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Финализация регистрации"""
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)  # ASYNC
    
    success = await AdminService.send_approval_request(context, context.user_data, user_id)
    
    if success:
        text = get_text('auth_pending_approval', lang)
    else:
        text = "❌ Ошибка при отправке запроса. Попробуйте позже."
    
    query = update.callback_query
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def cancel_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена процесса авторизации"""
    query = update.callback_query
    await query.answer("❌ Регистрация отменена")
    context.user_data.clear()
    
    from bot.handlers.common import back_to_start
    await back_to_start(update, context)
    return ConversationHandler.END

def create_auth_conversation():
    """Создание ConversationHandler для авторизации"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_auth, pattern="^start_auth$")
        ],
        states={
            SELECTING_ROLE: [
                CallbackQueryHandler(select_role, pattern="^auth_")
            ],
            GETTING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)
            ],
            GETTING_CONTACT: [
                MessageHandler(filters.CONTACT, get_contact)
            ],
            SELECTING_MANAGER_LEVEL: [
                CallbackQueryHandler(handle_manager_level, pattern="^level_")
            ],
            SELECTING_DISCIPLINE: [
                CallbackQueryHandler(handle_discipline, pattern="^disc_")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_auth, pattern="^cancel_auth$")
        ],
        per_user=True, per_chat=True, per_message=False, allow_reentry=True, name="auth_conversation"
    )