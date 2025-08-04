# bot/conversations/roster_flow.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler

from bot.middleware.security import check_user_role
from services.roster_service import RosterService
from utils.chat_utils import auto_clean
from utils.localization import get_user_language, get_text
from utils.constants import AWAITING_ROLES_COUNT, CONFIRM_ROSTER, CONFIRM_DANGEROUS_ROSTER_SAVE

logger = logging.getLogger(__name__)

@auto_clean
async def start_roster_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало подачи табеля (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = await get_user_language(user_id)
    
    # Проверяем, что пользователь - бригадир
    if not (user_role.get('isForeman') or user_role.get('isBrigade')):
        await query.edit_message_text("⛔️ Только бригадиры могут подавать табели.")
        return ConversationHandler.END
    
    # Проверяем статус табеля на сегодня
    roster_status = await RosterService.get_roster_status(user_id)
    
    if roster_status['exists']:
        total_people = roster_status['total_people']
        details = roster_status['details']
        
        details_text = "\n".join([f"  - {role}: {count} чел." for role, count in details.items()])
        
        text = (
            f"✅ **Табель на сегодня уже подан**\n\n"
            f"📊 **Итого людей:** {total_people}\n\n"
            f"**Детализация:**\n{details_text}\n\n"
            f"Хотите подать новый табель? (старый будет заменен)"
        )
        
        keyboard = [
            [InlineKeyboardButton("📝 Подать новый", callback_data="roster_submit_new")],
            [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_start")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    
    # Получаем доступные роли
    available_roles = await RosterService.get_available_roles()
    
    if not available_roles:
        await query.edit_message_text("❌ Ошибка: не найдены роли персонала в системе.")
        return ConversationHandler.END
    
    # Сохраняем роли в контекст
    context.user_data['available_roles'] = available_roles
    
    # Формируем текст с примером
    roles_list = "\n".join([f"  - {role['name']}" for role in available_roles])
    
    text = (
        f"📋 **Подача табеля учета рабочего времени**\n\n"
        f"**Доступные роли:**\n{roles_list}\n\n"
        f"**Введите количество людей по ролям в формате:**\n"
        f"`Сварщик 6 разряда 3`\n"
        f"`Помощник сварщика 2`\n"
        f"`Слесарь-монтажник 1`\n\n"
        f"💡 Одна роль на строку, в конце строки - количество человек."
    )
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return AWAITING_ROLES_COUNT

@auto_clean
async def process_roles_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ролей и количества (адаптировано из старого кода)"""
    user_input = update.message.text
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)
    
    available_roles = context.user_data.get('available_roles', [])
    
    # Парсим ввод
    parsed_roles = RosterService.parse_roles_input(user_input, available_roles)
    
    if not parsed_roles:
        await update.message.reply_text(
            "❌ **Ошибка формата**\n\n"
            "Проверьте ввод. Пример правильного формата:\n"
            "`Сварщик 6 разряда 3`\n"
            "`Помощник сварщика 2`\n\n"
            "Попробуйте еще раз:",
            parse_mode=ParseMode.MARKDOWN
        )
        return AWAITING_ROLES_COUNT
    
    # Подсчитываем сводку
    roster_summary = RosterService.calculate_roster_summary(parsed_roles)
    context.user_data['roster_summary'] = roster_summary
    
    # Формируем текст подтверждения
    total_people = roster_summary['total']
    details_text = "\n".join([f"  - **{role}**: {count} чел." for role, count in parsed_roles.items()])
    
    summary_text = (
        f"📊 **Подтверждение табеля**\n\n"
        f"**Всего людей:** {total_people}\n\n"
        f"**Детализация:**\n{details_text}\n\n"
        f"Все верно?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Да, сохранить", callback_data="confirm_roster")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_roster")]
    ]
    
    await update.message.reply_text(summary_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_ROSTER

@auto_clean
async def confirm_roster_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверяет безопасность и сохраняет табель (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = await check_user_role(user_id)
    lang = await get_user_language(user_id)
    
    roster_summary = context.user_data.get('roster_summary')
    
    if not roster_summary:
        await query.edit_message_text("❌ Данные табеля не найдены.")
        return ConversationHandler.END
    
    # Получаем название бригады
    brigade_name = user_role.get('brigadeName') or f"Бригада пользователя {user_id}"
    total_people_new = roster_summary['total']
    
    # Проверяем безопасность сохранения
    safety_check = await RosterService.check_roster_safety(user_id, total_people_new, brigade_name)
    
    if safety_check['is_safe']:
        # Безопасно сохраняем
        reserve = safety_check['reserve']
        
        if RosterService.save_roster(user_id, roster_summary):
            greeting_text = (
                f"✅ **Табель успешно сохранен!**\n\n"
                f"👥 Всего людей: **{total_people_new}**\n"
                f"📊 Резерв: **{reserve} чел.**"
            )
        else:
            greeting_text = "❌ Произошла ошибка при сохранении табеля."
        
        context.user_data.clear()
        await query.edit_message_text(greeting_text, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    else:
        # Требуется подтверждение
        total_assigned = safety_check['total_assigned']
        
        warning_text = (
            f"⚠️ **ВНИМАНИЕ!**\n\n"
            f"Новый табель: **{total_people_new} чел.**\n"
            f"Уже назначено в отчетах: **{total_assigned} чел.**\n\n"
            f"💡 Сохранение табеля **удалит все отчеты** за сегодня!\n\n"
            f"Продолжить?"
        )
        
        keyboard = [
            [InlineKeyboardButton("⚠️ Да, сохранить принудительно", callback_data="force_save_roster")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_roster")]
        ]
        
        await query.edit_message_text(warning_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return CONFIRM_DANGEROUS_ROSTER_SAVE

@auto_clean
async def force_save_roster(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Принудительно сохраняет табель, удаляя отчеты (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = await check_user_role(user_id)
    lang = await get_user_language(user_id)
    
    roster_summary = context.user_data.get('roster_summary')
    brigade_name = user_role.get('brigadeName') or f"Бригада пользователя {user_id}"
    
    if await RosterService.force_save_with_reports_deletion(user_id, roster_summary, brigade_name):
        greeting_text = (
            f"✅ **Табель принудительно сохранен!**\n\n"
            f"⚠️ Отчеты за сегодня были удалены.\n"
            f"👥 Всего людей: **{roster_summary['total']}**"
        )
    else:
        greeting_text = "❌ Произошла ошибка при принудительном сохранении."
    
    context.user_data.clear()
    await query.edit_message_text(greeting_text, parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

@auto_clean
async def cancel_roster_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет подачу табеля"""
    query = update.callback_query
    await query.answer()
    lang = await get_user_language(str(query.from_user.id))
    
    context.user_data.clear()
    await query.edit_message_text("❌ Подача табеля отменена.")
    return ConversationHandler.END

@auto_clean
async def restart_roster_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Перезапускает подачу табеля (для случая замены существующего)"""
    query = update.callback_query
    await query.answer()
    
    # Очищаем данные и начинаем заново
    context.user_data.clear()
    return await start_roster_submission(update, context)

def create_roster_conversation() -> ConversationHandler:
    """Создает ConversationHandler для системы табелей"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_roster_submission, pattern="^submit_roster$"),
            CallbackQueryHandler(restart_roster_submission, pattern="^roster_submit_new$")
        ],
        states={
            AWAITING_ROLES_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_roles_input)
            ],
            CONFIRM_ROSTER: [
                CallbackQueryHandler(confirm_roster_save, pattern="^confirm_roster$")
            ],
            CONFIRM_DANGEROUS_ROSTER_SAVE: [
                CallbackQueryHandler(force_save_roster, pattern="^force_save_roster$")
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_roster_submission, pattern="^cancel_roster$"),
            CommandHandler('start', lambda u, c: ConversationHandler.END)
        ],
        per_user=True,
    )