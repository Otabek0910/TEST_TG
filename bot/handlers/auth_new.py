# bot/handlers/auth_new.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ContextTypes

from bot.middleware.state_manager import StateManager, UserState, StateDecorator
from config.settings import OWNER_ID
from utils.localization import get_text, get_user_language
from utils.chat_utils import auto_clean
from database.queries import db_query
from services.admin_service import AdminService

logger = logging.getLogger(__name__)

# ============================================================================
# ENTRY POINT
# ============================================================================


async def start_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало авторизации - НАДЕЖНАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)
    
    # Устанавливаем состояние
    StateManager.set_state(context, user_id, UserState.SELECTING_ROLE)
    
    keyboard = [
        [InlineKeyboardButton("👨‍🔧 Супервайзер", callback_data="auth_supervisor")],
        [InlineKeyboardButton("🔨 Мастер", callback_data="auth_master")],
        [InlineKeyboardButton("👷 Бригадир", callback_data="auth_foreman")],
        [InlineKeyboardButton("📊 КИОК", callback_data="auth_kiok")],
        [InlineKeyboardButton("🏭 ПТО", callback_data="auth_pto")],
        [InlineKeyboardButton("👨‍💼 Менеджер", callback_data="auth_manager")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_auth")]
    ]
    
    await query.edit_message_text(
        text=get_text('auth_prompt_role', lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

# ============================================================================
# ROLE SELECTION  
# ============================================================================


@StateDecorator.require_state(UserState.SELECTING_ROLE)
async def select_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор роли - с проверкой состояния"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)
    
    selected_role = query.data.replace('auth_', '')
    
    # Сохраняем выбранную роль
    StateManager.update_state_data(context, user_id, {'selected_role': selected_role})
    
    # Переходим к запросу имени
    StateManager.set_state(context, user_id, UserState.GETTING_NAME)

    sent_message = await query.edit_message_text(
        text=get_text('auth_prompt_name', lang),
        parse_mode=ParseMode.HTML
    )
    StateManager.update_state_data(context, user_id, {'last_prompt_id': sent_message.message_id})

# ============================================================================
# NAME INPUT
# ============================================================================

@StateDecorator.require_state(UserState.GETTING_NAME)
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение имени - с проверкой состояния"""
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)

        # FIXED: Удаляем предыдущее сообщение с подсказкой
    state_data = StateManager.get_state_data(context, user_id)
    last_prompt_id = state_data.get('last_prompt_id')
    if last_prompt_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=last_prompt_id)
        except Exception:
            pass
    
    # Удаляем сообщение пользователя
    await update.message.delete()
    
    user_input = update.message.text.strip()
    if ' ' not in user_input or len(user_input.split()) < 2:
        sent_message = await context.bot.send_message(
            update.effective_chat.id,
            get_text('auth_error_name', lang),
            parse_mode=ParseMode.HTML
        )

        StateManager.update_state_data(context, user_id, {'last_prompt_id': sent_message.message_id})
        # НЕ меняем состояние - остаемся в GETTING_NAME
        return
    
    parts = user_input.split(' ', 1)
    
    # Сохраняем имя и фамилию
    StateManager.update_state_data(context, user_id, {
        'first_name': parts[0],
        'last_name': parts[1]
    })
    
    # Переходим к запросу контакта
    StateManager.set_state(context, user_id, UserState.GETTING_CONTACT)
    
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
    StateManager.update_state_data(context, user_id, {'last_prompt_id': sent_message.message_id})

# ============================================================================
# CONTACT INPUT
# ============================================================================


@StateDecorator.require_state(UserState.GETTING_CONTACT)
async def get_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение контакта - с проверкой состояния и очисткой сообщений"""
    user_id = str(update.effective_user.id)

     # 1. Удаляем предыдущее сообщение бота (просьбу отправить контакт)
    state_data = StateManager.get_state_data(context, user_id)
    last_prompt_id = state_data.get('last_prompt_id')
    if last_prompt_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=last_prompt_id)
        except Exception:
            pass # Игнорируем ошибку, если сообщение уже удалено

    # 2. Удаляем сообщение пользователя с самим контактом
    await update.message.delete()

    # --- КОНЕЦ ИЗМЕНЕНИЙ ---

    # Удаляем клавиатуру "Поделиться контактом", отправив временное сообщение
    temp_msg = await context.bot.send_message(
        update.effective_chat.id,
        "⏳ Обрабатываю...",
        reply_markup=ReplyKeyboardRemove()
    )

    # Удаляем это временное сообщение
    await context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=temp_msg.message_id
    )

    # Сохраняем номер телефона в состоянии
    if update.message.contact:
        StateManager.update_state_data(context, user_id, {
            'phone_number': update.message.contact.phone_number
        })

    # Получаем роль и решаем, что делать дальше
    current_state_data = StateManager.get_state_data(context, user_id)
    role = current_state_data.get('selected_role')

    if role == 'manager':
        await handle_manager_level_selection(update, context)
    else:
        await handle_discipline_selection(update, context)

# ============================================================================
# MANAGER LEVEL
# ============================================================================

async def handle_manager_level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора уровня менеджера"""
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)
    
    StateManager.set_state(context, user_id, UserState.SELECTING_MANAGER_LEVEL)
    
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

@StateDecorator.require_state(UserState.SELECTING_MANAGER_LEVEL)
async def handle_manager_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор уровня менеджера"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    level = int(query.data.replace('level_', ''))
    
    StateManager.update_state_data(context, user_id, {'manager_level': level})
    
    if level == 1:
        # Уровень 1 - сразу финализируем
        await finalize_registration(update, context)
    else:
        # Уровень 2 - нужна дисциплина
        await handle_discipline_selection(update, context)

# ============================================================================
# DISCIPLINE SELECTION
# ============================================================================

async def handle_discipline_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор дисциплины"""
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)
    
    StateManager.set_state(context, user_id, UserState.SELECTING_DISCIPLINE)
    
    disciplines = await db_query("SELECT id, name FROM disciplines ORDER BY name")
    
    if not disciplines:
        await context.bot.send_message(
            update.effective_chat.id,
            "❌ Ошибка: дисциплины не найдены в системе."
        )
        return
    
    keyboard = [[InlineKeyboardButton(name, callback_data=f"disc_{disc_id}")] 
                for disc_id, name in disciplines]
    
    state_data = StateManager.get_state_data(context, user_id)
    role_key = state_data.get('selected_role', '')
    
    role_map_loc = {
        'supervisor': 'супервайзера', 'master': 'мастера', 'manager': 'менеджера',
        'foreman': 'бригадира', 'kiok': 'КИОК', 'pto': 'ПТО'
    }
    role_for_text = role_map_loc.get(role_key, role_key)
    
    text_template = get_text('auth_prompt_discipline', lang)
    text = text_template.format(role=role_for_text)
    
    # Определяем куда отправлять
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode=ParseMode.HTML
        )
    else:
        await context.bot.send_message(
            update.effective_chat.id,
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )

@StateDecorator.require_state(UserState.SELECTING_DISCIPLINE)
async def handle_discipline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор дисциплины"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    discipline_id = query.data.replace('disc_', '')
    
    StateManager.update_state_data(context, user_id, {'discipline_id': discipline_id})
    
    await finalize_registration(update, context)

# ============================================================================
# FINALIZATION
# ============================================================================

@StateDecorator.clear_state_after
async def finalize_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Финализация регистрации с очисткой состояния"""
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)
    
    # Получаем все данные
    user_data = StateManager.get_state_data(context, user_id)
    
    # Отправляем заявку админам
    success = await AdminService.send_approval_request(context, user_data, user_id)
    
    if success:
        text = get_text('auth_pending_approval', lang)
    else:
        text = "❌ Ошибка при отправке запроса. Попробуйте позже."
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML)
    else:
        await context.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.HTML)

# ============================================================================
# CANCELLATION
# ============================================================================

@StateDecorator.clear_state_after
async def cancel_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена авторизации с очисткой состояния"""
    query = update.callback_query
    await query.answer("❌ Регистрация отменена")
    
    from bot.handlers.common import back_to_start
    await back_to_start(update, context)

# ============================================================================
# REGISTRATION
# ============================================================================

def register_new_auth_handlers(application):
    """Регистрация НАДЕЖНЫХ auth handlers"""
    
    # Entry point
    application.add_handler(CallbackQueryHandler(start_auth, pattern="^start_auth$"))
    
    # Role selection
    application.add_handler(CallbackQueryHandler(select_role, pattern="^auth_"))
    
    # Text inputs - БЕЗ ConversationHandler!
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_name))
    application.add_handler(MessageHandler(filters.CONTACT, get_contact))
    
    # Selections
    application.add_handler(CallbackQueryHandler(handle_manager_level, pattern="^level_"))
    application.add_handler(CallbackQueryHandler(handle_discipline, pattern="^disc_"))
    
    # Cancellation
    application.add_handler(CallbackQueryHandler(cancel_auth, pattern="^cancel_auth$"))
    
    logger.info("✅ NEW Auth handlers зарегистрированы (БЕЗ ConversationHandler)")