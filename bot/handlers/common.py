"""
Общие handlers (start, main menu, etc.)
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes

# Импорты из нашего проекта
from config.settings import OWNER_ID, REPORTS_GROUP_URL
from services.user_service import UserService
from services.menu_service import MenuService
from bot.middleware.security import check_user_role
from utils.chat_utils import auto_clean  # <-- Импортируем наш НОВЫЙ декоратор
from utils.localization import get_user_language, get_user_language_sync

logger = logging.getLogger(__name__)



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = str(user.id)
    
    logger.info(f"Пользователь {user_id} ({user.first_name}) запустил бота")
    
    welcome_text, keyboard_buttons = await MenuService.get_main_menu_text_and_buttons(user_id)
    
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    
    
    # Просто отправляем сообщение и ВОЗВРАЩАЕМ его, чтобы декоратор мог его отследить
    return await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        
    )


async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к стартовому меню"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    
    welcome_text, keyboard_buttons = await MenuService.get_main_menu_text_and_buttons(user_id)
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    # Просто редактируем сообщение и ВОЗВРАЩАЕМ его
    return await query.edit_message_text(
        welcome_text,
        reply_markup=reply_markup,
        
    )

# --- Остальные обработчики ---


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ профиля пользователя - УЛУЧШЕННАЯ ВЕРСИЯ"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    user_role = check_user_role(user_id)  # СИНХРОННЫЙ вызов
    lang = await get_user_language(user_id)  # АСИНХРОННЫЙ вызов
    
    user_info = await UserService.get_user_info(user_id)
    
    if user_info:
        # Определяем заголовок
        if user_info.get('role_table') == 'owner':
            profile_text = "👑 **Профиль владельца системы**\n\n"
        else:
            profile_text = "👤 **Ваш профиль**\n\n"
        
        # FIXED: Используем правильные поля
        first_name = user_info.get('first_name', '')
        last_name = user_info.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()
        
        profile_text += f"📝 **Имя:** {full_name if full_name else 'Не указано'}\n"
        profile_text += f"📞 **Телефон:** {user_info.get('phone_number', 'Не указан')}\n"
        
        # ADDED: Показываем дисциплину
        discipline = user_info.get('discipline_name', 'Не указана')
        profile_text += f"🏢 **Дисциплина:** {discipline}\n"
        
        # FIXED: Получаем роль
        role_info = MenuService._get_user_role_info(user_role, lang)
        if role_info:
            profile_text += f"👔 **Роль:** {role_info}\n"
        else:
            profile_text += f"👔 **Роль:** Не определена\n"
            
        # ADDED: Дополнительная информация для Owner
        if user_info.get('role_table') == 'owner':
            profile_text += f"\n🔑 **Привилегии:** Полный доступ ко всем функциям\n"
            profile_text += f"⚙️ **Статус:** Владелец системы\n"
            
    else:
        profile_text = "❌ **Информация о пользователе не найдена**\n\nОбратитесь к администратору."
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")]]
    return await query.edit_message_text(
        profile_text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )



async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показ информации о боте для неавторизованных пользователей"""
    query = update.callback_query
    await query.answer()
    
    info_text = "ℹ️ **Информация о боте**\n\nДля начала работы пройдите авторизацию."
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")]]
    return await query.edit_message_text(info_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def placeholder_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Универсальная заглушка для функций в разработке"""
    query = update.callback_query
    await query.answer()
    
    text = "🚧 **Раздел в разработке**\n\nЭта функция скоро появится!"
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")]]
    return await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def show_language_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора языка"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    current_lang = await get_user_language(user_id)
    
    # Доступные языки
    languages = {
        'ru': '🇷🇺 Русский',
        'en': '🇺🇸 English', 
        'uz': '🇺🇿 O\'zbekcha'
    }
    
    keyboard_buttons = []
    for lang_code, lang_name in languages.items():
        # Помечаем текущий язык
        if lang_code == current_lang:
            lang_name += " ✅"
        
        keyboard_buttons.append([InlineKeyboardButton(
            lang_name, 
            callback_data=f"set_language_{lang_code}"
        )])
    
    keyboard_buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")])
    
    text = "🌐 **Выбор языка / Language Selection / Til tanlash**"
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode='Markdown'
    )


async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает смену языка"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем выбранный язык
    lang_code = query.data.split('_')[-1]
    user_id = str(query.from_user.id)
    
    # Обновляем язык пользователя
    from utils.localization import update_user_language
    await update_user_language(user_id, lang_code)
    
    # Уведомляем о смене языка
    success_messages = {
        'ru': '✅ Язык изменен на русский',
        'en': '✅ Language changed to English',
        'uz': '✅ Til o\'zbekchaga o\'zgartirildi'
    }
    
    await query.edit_message_text(success_messages.get(lang_code, '✅ Language changed'))
    
    # Возвращаемся в главное меню с новым языком
    await back_to_start(update, context)

def register_common_handlers(application):
    """Регистрация общих handlers"""
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(back_to_start, pattern="^back_to_start$"))
    
    application.add_handler(CallbackQueryHandler(show_info, pattern="^show_info$"))
    application.add_handler(CallbackQueryHandler(show_profile, pattern="^show_profile$"))
    
     # НОВЫЕ обработчики языка
    application.add_handler(CallbackQueryHandler(show_language_menu, pattern="^change_language$"))
    application.add_handler(CallbackQueryHandler(change_language, pattern="^set_language_"))


    # Заглушки для функций в разработке
    placeholders = [
        "owner_reports_menu", "owner_management_menu",
        "reports_menu_role", "admin_panel"
    ]
    for ph in placeholders:
        application.add_handler(CallbackQueryHandler(placeholder_handler, pattern=f"^{ph}$"))

    from bot.conversations.roster_flow import create_roster_conversation
    application.add_handler(create_roster_conversation())

    logger.info("✅ Common handlers зарегистрированы")