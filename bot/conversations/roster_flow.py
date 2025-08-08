# bot/conversations/roster_flow.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters, CommandHandler

from bot.middleware.security import check_user_role
from services.roster_service import RosterService
from utils.chat_utils import auto_clean
from utils.localization import get_user_language, get_text

# FIXED: Правильный импорт ВСЕХ констант
from utils.constants import (
    AWAITING_ROLES_COUNT, CONFIRM_ROSTER, CONFIRM_DANGEROUS_ROSTER_SAVE,
    AWAITING_MODE_SELECTION, INTERACTIVE_ROSTER_EDIT
)

logger = logging.getLogger(__name__)

@auto_clean
async def start_roster_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало подачи табеля - ВЫБОР РЕЖИМА"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    
    # Проверяем, что пользователь - бригадир
    if not (user_role.get('isForeman') or user_role.get('isBrigade')):
        await query.edit_message_text("⛔️ Только бригадиры могут подавать табели.")
        return ConversationHandler.END
    
    # Проверяем статус табеля на сегодня (существующая логика)
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
    
    # ДОБАВЛЯЕМ: Выбор режима подачи табеля
    keyboard = [
        [InlineKeyboardButton("🎯 Быстрый режим (кнопки)", callback_data="roster_mode_interactive")],
        [InlineKeyboardButton("📝 Текстовый режим", callback_data="roster_mode_text")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        "📋 **Выберите способ подачи табеля:**\n\n"
        "🎯 **Быстрый режим** - кнопки +/- для каждой роли\n"
        "📝 **Текстовый режим** - ввод текстом как раньше",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return AWAITING_MODE_SELECTION 

async def select_roster_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора режима подачи табеля"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "roster_mode_interactive":
        return await start_interactive_mode(update, context)
    elif query.data == "roster_mode_text":
        return await start_text_mode(update, context)
    else:
        await query.edit_message_text("❌ Неизвестный режим")
        return ConversationHandler.END

    
async def start_interactive_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск интерактивного режима"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    # FIXED: Получаем роли ДЛЯ ДИСЦИПЛИНЫ бригадира
    available_roles = await RosterService.get_available_roles(user_id)
    
    if not available_roles:
        await query.edit_message_text("❌ Ошибка: не найдены роли персонала для вашей дисциплины.")
        return ConversationHandler.END
    
    # Ограничиваем количество ролей для экономии памяти
    if len(available_roles) > 8:
        available_roles = available_roles[:8]
    
    # Инициализируем счетчики ролей
    context.user_data['roster_counts'] = {role['id']: 0 for role in available_roles}
    context.user_data['available_roles'] = available_roles
    
    return await show_interactive_roster_edit(update, context)

async def start_text_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запуск текстового режима (существующая логика)"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    # FIXED: Получаем роли ДЛЯ ДИСЦИПЛИНЫ бригадира
    available_roles = await RosterService.get_available_roles(user_id)
    
    if not available_roles:
        await query.edit_message_text("❌ Ошибка: не найдены роли персонала для вашей дисциплины.")
        return ConversationHandler.END
    
    # Сохраняем роли в контекст
    context.user_data['available_roles'] = available_roles
    
    # Формируем текст с примером
    discipline_name = available_roles[0]['discipline'] if available_roles else 'Неизвестная'
    roles_list = "\n".join([f"  - {role['name']}" for role in available_roles])
    
    text = (
        f"📋 **Подача табеля для дисциплины «{discipline_name}»**\n\n"
        f"**Доступные роли:**\n{roles_list}\n\n"
        f"**Введите количество людей по ролям в формате:**\n"
        f"`Сварщик 6 разряда 3`\n"
        f"`Помощник сварщика 2`\n\n"
        f"💡 Одна роль на строку, в конце строки - количество человек."
    )
    
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return AWAITING_ROLES_COUNT

async def show_interactive_roster_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает КОМПАКТНОЕ интерактивное окно табеля"""
    query = update.callback_query if hasattr(update, 'callback_query') and update.callback_query else None
    
    available_roles = context.user_data.get('available_roles', [])
    roster_counts = context.user_data.get('roster_counts', {})
    
    if not available_roles:
        if query:
            await query.edit_message_text("❌ Ошибка: роли не найдены")
        return ConversationHandler.END
    
    # Компактный формат отображения
    discipline_name = available_roles[0]['discipline'] if available_roles else 'Неизвестная'
    
    text_lines = [f"📋 *Табель: {discipline_name}*\n"]
    
    total_people = 0
    for role in available_roles:
        role_id = role['id']
        count = roster_counts.get(role_id, 0)
        total_people += count
        
        # Сокращаем название роли
        short_name = role['name']
        if len(short_name) > 20:
            short_name = short_name[:17] + "..."
        
        # Используем эмодзи для визуализации
        status_emoji = "✅" if count > 0 else "⚪"
        text_lines.append(f"{status_emoji} {short_name}: *{count}*")
    
    text_lines.append(f"\n👥 *Итого: {total_people} чел.*")
    
    # Компактная сетка кнопок 2x3
    keyboard = []
    
    for i in range(0, len(available_roles), 2):
        row = []
        
        # Первая роль в строке
        role1 = available_roles[i]
        count1 = roster_counts.get(role1['id'], 0)
        role1_short = role1['name'][:8] + "..." if len(role1['name']) > 8 else role1['name']
        
        row.extend([
            InlineKeyboardButton("➖", callback_data=f"r-_{role1['id']}"),
            InlineKeyboardButton(f"{role1_short}:{count1}", callback_data=f"r_info_{role1['id']}"),
            InlineKeyboardButton("➕", callback_data=f"r+_{role1['id']}")
        ])
        
        # Вторая роль в строке (если есть)
        if i + 1 < len(available_roles):
            role2 = available_roles[i + 1]
            count2 = roster_counts.get(role2['id'], 0)
            role2_short = role2['name'][:8] + "..." if len(role2['name']) > 8 else role2['name']
            
            row.extend([
                InlineKeyboardButton("➖", callback_data=f"r-_{role2['id']}"),
                InlineKeyboardButton(f"{role2_short}:{count2}", callback_data=f"r_info_{role2['id']}"),
                InlineKeyboardButton("➕", callback_data=f"r+_{role2['id']}")
            ])
        
        keyboard.append(row)
    
    # Кнопки управления
    control_row = []
    if total_people > 0:
        control_row.append(InlineKeyboardButton("✅ Сохранить", callback_data="r_save"))
    control_row.append(InlineKeyboardButton("❌ Отмена", callback_data="r_cancel"))
    keyboard.append(control_row)
    
    text = "\n".join(text_lines)
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    return INTERACTIVE_ROSTER_EDIT

async def handle_roster_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает нажатия кнопок +/- в табеле"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    roster_counts = context.user_data.get('roster_counts', {})
    
    # FIXED: Правильная обработка кнопок
    if data.startswith('r+_'):
        role_id = int(data.replace('r+_', ''))
        if role_id in roster_counts:
            if roster_counts[role_id] < 20:  # максимум 20 человек
                roster_counts[role_id] += 1
                context.user_data['roster_counts'] = roster_counts
        
    elif data.startswith('r-_'):
        role_id = int(data.replace('r-_', ''))
        if role_id in roster_counts:
            if roster_counts[role_id] > 0:
                roster_counts[role_id] -= 1
                context.user_data['roster_counts'] = roster_counts
                
    elif data == 'r_save':
        return await save_interactive_roster(update, context)
        
    elif data == 'r_cancel':
        await query.edit_message_text("❌ Подача табеля отменена.")
        # Очищаем данные
        context.user_data.pop('roster_counts', None)
        context.user_data.pop('available_roles', None)
        return ConversationHandler.END
        
    elif data.startswith('r_info_'):
        # Показываем полное название роли
        role_id = int(data.replace('r_info_', ''))
        available_roles = context.user_data.get('available_roles', [])
        role = next((r for r in available_roles if r['id'] == role_id), None)
        if role:
            await query.answer(f"📋 {role['name']}", show_alert=True)
        return INTERACTIVE_ROSTER_EDIT
    
    # Обновляем интерфейс
    return await show_interactive_roster_edit(update, context)

async def save_interactive_roster(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет табель из интерактивного интерфейса"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    available_roles = context.user_data.get('available_roles', [])
    roster_counts = context.user_data.get('roster_counts', {})
    
    # Формируем данные для сохранения
    parsed_roles = {}
    for role in available_roles:
        count = roster_counts.get(role['id'], 0)
        if count > 0:
            parsed_roles[role['name']] = count
    
    if not parsed_roles:
        await query.answer("❌ Нужно указать хотя бы одну роль!", show_alert=True)
        return INTERACTIVE_ROSTER_EDIT
    
    # Сохраняем через RosterService
    roster_summary = RosterService.calculate_roster_summary(parsed_roles)
    success = await RosterService.save_roster(user_id, roster_summary)
    
    if success:
        total_people = roster_summary['total']
        details_text = "\n".join([f"• {role}: {count}" for role, count in parsed_roles.items()])
        
        await query.edit_message_text(
            f"✅ *Табель сохранен!*\n\n"
            f"👥 *Всего: {total_people} чел.*\n\n"
            f"*Состав:*\n{details_text}",
            parse_mode='Markdown'
        )
    else:
        await query.edit_message_text("❌ Ошибка сохранения. Попробуйте еще раз.")
        return INTERACTIVE_ROSTER_EDIT
    
    # Очищаем данные после сохранения
    context.user_data.pop('roster_counts', None)
    context.user_data.pop('available_roles', None)
    
    return ConversationHandler.END

@auto_clean
async def process_roles_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает ввод ролей и количества"""
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
    """Проверяет безопасность и сохраняет табель"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)  # FIXED: убираем await
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
        
        if await RosterService.save_roster(user_id, roster_summary):  # FIXED: добавляем await
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
    """Принудительно сохраняет табель, удаляя отчеты"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)  # FIXED: убираем await
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
    
    context.user_data.clear()
    await query.edit_message_text("❌ Подача табеля отменена.")
    return ConversationHandler.END
@auto_clean
async def restart_roster_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Перезапускает подачу табеля"""
    query = update.callback_query
    await query.answer()
    
    # Очищаем данные и начинаем заново
    context.user_data.clear()
    return await start_roster_submission(update, context)

def create_roster_conversation() -> ConversationHandler:
    """Создает ConversationHandler для системы табелей - ПОЛНАЯ ВЕРСИЯ"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_roster_submission, pattern="^submit_roster$"),
            CallbackQueryHandler(restart_roster_submission, pattern="^roster_submit_new$")
        ],
        states={
            # ADDED: Выбор режима
            AWAITING_MODE_SELECTION: [
                CallbackQueryHandler(select_roster_mode, pattern="^roster_mode_")
            ],
            
            # Текстовый режим (существующие состояния)
            AWAITING_ROLES_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_roles_input)
            ],
            CONFIRM_ROSTER: [
                CallbackQueryHandler(confirm_roster_save, pattern="^confirm_roster$")
            ],
            CONFIRM_DANGEROUS_ROSTER_SAVE: [
                CallbackQueryHandler(force_save_roster, pattern="^force_save_roster$")
            ],
            
            # ADDED: Интерактивный режим
            INTERACTIVE_ROSTER_EDIT: [
                CallbackQueryHandler(handle_roster_button, pattern="^r")  # FIXED: правильный паттерн
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_roster_submission, pattern="^cancel_roster$"),
            CommandHandler('start', lambda u, c: ConversationHandler.END)
        ],
        per_user=True,
    )