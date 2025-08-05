# bot/handlers/approval.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes

from config.settings import OWNER_ID
from database.queries import db_query
from ..middleware.security import check_user_role
from services.admin_service import AdminService

logger = logging.getLogger(__name__)

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка одобрения/отклонения заявки с проверкой на дубликаты."""
    query = update.callback_query
    print(f"DEBUG >>> КНОПКА НАЖАТА! ДАННЫЕ: {query.data}")
   
    approver_id = str(query.from_user.id)
    
    user_role = check_user_role(approver_id)
    if not (user_role.get('isAdmin') or approver_id == OWNER_ID):
        await query.answer("❌ У вас нет прав для выполнения этого действия", show_alert=True)
        return
    
    await query.answer()
    
    try:
        parts = query.data.split('_')
        action, _, user_id = parts[0], parts[1], parts[2]
    except (IndexError, ValueError):
        await query.edit_message_text("❌ Некорректные данные запроса.")
        return
    
    user_data = context.bot_data.get(user_id)
    if not user_data:
        await query.edit_message_text("⚠️ Данные пользователя не найдены (запрос устарел).")
        return

    # FIXED: Получаем роль из сохраненных данных, а не из callback
    role = user_data.get('selected_role')
    if not role:
        await query.edit_message_text("❌ Ошибка: роль пользователя не найдена в сохраненных данных.")
        return
    
    # Карта ролей для текста и имени таблицы
    role_map = {
        'foreman': ('Бригадир', 'brigades'), 'manager': ('Менеджер', 'managers'), 
        'pto': ('ПТО', 'pto'), 'kiok': ('КИОК', 'kiok'), 
        'supervisor': ('Супервайзер', 'supervisors'), 'master': ('Мастер', 'masters')
    }
    role_text, table_name = role_map.get(role, (role.capitalize(), None))
    
    if action == 'approve':
        # --- FIXED: Добавлена проверка на существование пользователя ---
        if table_name:
            user_exists = await db_query(f"SELECT 1 FROM {table_name} WHERE user_id = %s", (user_id,))
            if user_exists:
                admin_text = f"⚠️ **Действие не требуется.**\n\nПользователь уже существует с ролью «{role_text}»."
                await query.edit_message_text(admin_text, parse_mode=ParseMode.HTML)
                return
        # --- Конец проверки ---

        success = await AdminService.create_user_in_db(user_data, user_id)
        
        if success:
            admin_text = f"✅ <b>Заявка одобрена</b>\n\nПользователь {user_data.get('first_name', '')} добавлен с ролью «{role_text}»."
            await query.edit_message_text(admin_text, parse_mode=ParseMode.HTML)
            
            # FIXED: Отправляем пользователю уведомление с правильным меню
            user_text = f"🎉 <b>Ваша заявка одобрена!</b>\n\nВам присвоена роль «{role_text}».\n\n✨ Добро пожаловать! Теперь вы можете пользоваться всеми функциями бота."
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")]]
            try:
                await context.bot.send_message(
                    user_id, 
                    user_text, 
                    reply_markup=InlineKeyboardMarkup(keyboard), 
                    parse_mode=ParseMode.HTML
                )
                logger.info(f"Уведомление об одобрении отправлено пользователю {user_id}")
            except Exception as e:
                logger.error(f"Не удалось уведомить пользователю {user_id}: {e}")
        else:
            await query.edit_message_text("❌ Ошибка при создании пользователя в БД.")
            
    elif action == 'reject':
        admin_text = f"❌ <b>Заявка отклонена</b> по роли «{role_text}»."
        await query.edit_message_text(admin_text, parse_mode=ParseMode.HTML)
        
        # FIXED: Уведомляем пользователя об отклонении
        user_text = f"😔 <b>Ваша заявка отклонена</b>\n\nРоль «{role_text}» не была присвоена.\n\nВы можете повторить авторизацию позже."
        keyboard = [[InlineKeyboardButton("🔑 Попробовать снова", callback_data="start_auth")]]
        try:
            await context.bot.send_message(
                user_id, 
                user_text, 
                reply_markup=InlineKeyboardMarkup(keyboard), 
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {user_id} об отклонении: {e}")
    
    # Очищаем временные данные в любом случае
    if user_id in context.bot_data:
        del context.bot_data[user_id]


def register_approval_handlers(application):
    """Регистрация handlers для одобрения заявок"""
    print("DEBUG >>> РЕГИСТРАЦИЯ ОБРАБОТЧИКА КНОПОК ОДОБРЕНИЯ...")
    application.add_handler(CallbackQueryHandler(handle_approval, pattern="^(approve|reject)_"))
    logger.info("✅ Approval handlers зарегистрированы")