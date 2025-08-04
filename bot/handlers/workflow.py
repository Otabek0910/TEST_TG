# bot/handlers/workflow.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
)

from bot.middleware.security import check_user_role  # СИНХРОННАЯ функция
from services.workflow_service import WorkflowService
from services.notification_service import NotificationService
from utils.chat_utils import auto_clean
from utils.localization import get_text, get_user_language
from utils.constants import (
    AWAITING_MASTER_REJECTION, AWAITING_KIOK_INSPECTION_NUM, AWAITING_KIOK_REJECTION
)
from database.queries import db_query_single  # АСИНХРОННАЯ функция

logger = logging.getLogger(__name__)

async def show_master_approval_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список отчетов для подтверждения мастера"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    pending_reports = await WorkflowService.get_pending_reports_for_master(user_id)  # ASYNC
    
    if not pending_reports:
        text = "Нет отчетов для подтверждения."
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")]]
    else:
        text = f"Отчеты на подтверждение ({len(pending_reports)} шт.):"
        keyboard = []
        for report in pending_reports:
            report_text = f"ID:{report['id']} - {report['brigade_name']} - {report['work_type_name']}"
            keyboard.append([InlineKeyboardButton(report_text, callback_data=f"master_view_{report['id']}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")])
    
    return await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def show_master_report_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали отчета для мастера"""
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split('_')[-1])
    
    report_details = await WorkflowService.get_report_details(report_id)  # ASYNC
    
    if not report_details:
        return await query.answer("❌ Отчет не найден", show_alert=True)
    
    report_data = report_details.get('report_data', {})
    text = f"*Отчет ID: {report_id}*\n" \
           f"Супервайзер: {report_details.get('supervisor_name', 'Неизвестно')}\n" \
           f"Бригада: {report_details.get('brigade_name')}\n" \
           f"Работы: {report_details.get('work_type_name')}\n" \
           f"Дата: {report_details.get('report_date').strftime('%d.%m.%Y')}\n\n" \
           f"*Данные:*\n"
    
    if 'pipe_diameter' in report_data:
        text += f" • Диаметр: {report_data['pipe_diameter']} мм\n"
        text += f" • Длина: {report_data['pipe_length']} м\n"
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"master_approve_{report_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"master_reject_{report_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="approve_reports")]
    ]
    
    return await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def master_approve_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мастер подтверждает отчет"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    report_id = int(query.data.split('_')[-1])
    
    success = await WorkflowService.master_approve(report_id, user_id)  # ASYNC
    
    if success:
        # FIXED: discipline_id получаем асинхронно
        discipline_id = await db_query_single("SELECT discipline_id FROM reports WHERE id = %s", (report_id,))
        if discipline_id:
            kiok_users = await NotificationService.get_users_for_discipline_notification(discipline_id, 'kiok')  # ASYNC
            for kiok_user in kiok_users:
                await NotificationService.notify_kiok_new_report(context, report_id, kiok_user)
        
        text = f"✅ Отчет ID:{report_id} подтвержден и отправлен в КИОК."
    else:
        text = "❌ Ошибка подтверждения отчета."
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="approve_reports")]]
    return await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def master_reject_report_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает причину отклонения у мастера"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    lang = await get_user_language(user_id)  # ASYNC
    report_id = int(query.data.split('_')[-1])
    
    context.user_data['rejecting_report_id'] = report_id
    context.user_data['rejecting_role'] = 'master'
    
    text = get_text('master_rejection_reason_prompt', lang)
    keyboard = [[InlineKeyboardButton(get_text('cancel_button', lang), callback_data="approve_reports")]]
    
    message = await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['rejection_message_id'] = message.message_id
    return AWAITING_MASTER_REJECTION

async def process_master_rejection_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает причину отклонения от мастера"""
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)  # ASYNC
    reason = update.message.text
    
    report_id = context.user_data.get('rejecting_report_id')
    if not report_id:
        return
    
    await update.message.delete()
    
    message_id = context.user_data.get('rejection_message_id')
    if message_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        except:
            pass
    
    success = await WorkflowService.master_reject(report_id, user_id, reason)  # ASYNC
    
    if success:
        await NotificationService.notify_supervisor_status_change(
            context, report_id, 'rejected', user_id, reason
        )
        
        text = get_text('master_rejection_success', lang).format(report_id=report_id)
    else:
        text = get_text('master_rejection_error', lang)
    
    keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="approve_reports")]]
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data.pop('rejecting_report_id', None)
    context.user_data.pop('rejecting_role', None)
    context.user_data.pop('rejection_message_id', None)
    return ConversationHandler.END

# ===== КИОК HANDLERS =====

async def show_kiok_review_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список отчетов для проверки КИОК"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    lang = await get_user_language(user_id)  # ASYNC
    user_role = check_user_role(user_id)  # СИНХРОННЫЙ вызов
    
    if not user_role.get('isKiok'):
        await query.answer("❌ У вас нет прав КИОК", show_alert=True)
        return
    
    pending_reports = await WorkflowService.get_pending_reports_for_kiok(user_id)  # ASYNC
    
    if not pending_reports:
        text = get_text('kiok_no_pending_reports', lang)
        keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="back_to_start")]]
    else:
        text = get_text('kiok_pending_reports_title', lang).format(count=len(pending_reports))
        keyboard = []
        
        for report in pending_reports:
            report_text = f"ID:{report['id']} - {report['brigade_name']} - {report['work_type_name']}"
            keyboard.append([
                InlineKeyboardButton(report_text, callback_data=f"kiok_view_{report['id']}")
            ])
        
        keyboard.append([InlineKeyboardButton(get_text('back_button', lang), callback_data="back_to_start")])
    
    return await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def show_kiok_report_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает детали отчета для КИОК"""
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split('_')[-1])

    report_details = await WorkflowService.get_report_details(report_id)  # ASYNC
    if not report_details:
        return await query.answer("❌ Отчет не найден", show_alert=True)

    report_data = report_details.get('report_data', {})
    master_signed_at = report_details.get('master_signed_at')
    
    text_lines = [
        f"*🔍 КИОК проверка отчета ID: {report_id}*",
        f"Супервайзер: {report_details.get('supervisor_name', 'Неизвестно')}",
        f"Бригада: {report_details.get('brigade_name')}",
        f"Работы: {report_details.get('work_type_name')}",
        f"Дата: {report_details.get('report_date').strftime('%d.%m.%Y')}",
        f"Подтвердил мастер: {report_details.get('master_name', 'Неизвестно')}",
        f"Время: {master_signed_at.strftime('%d.%m.%Y %H:%M') if master_signed_at else 'Н/Д'}",
        "\n*Данные работ:*"
    ]
    
    if 'pipe_diameter' in report_data:
        text_lines.append(f"  • Диаметр трубы: {report_data['pipe_diameter']} мм")
        text_lines.append(f"  • Длина участка: {report_data['pipe_length']} м")

    text = "\n".join(text_lines)
    
    keyboard = [
        [InlineKeyboardButton("✅ Согласовать", callback_data=f"kiok_approve_final_{report_id}")],
        [InlineKeyboardButton("❌ Отклонить", callback_data=f"kiok_reject_final_{report_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="kiok_review")]
    ]
    
    return await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def kiok_approve_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает номер проверки для согласования КИОК"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    lang = await get_user_language(user_id)  # ASYNC
    report_id = int(query.data.split('_')[-1])
    
    context.user_data['approving_report_id'] = report_id
    
    text = get_text('kiok_inspection_number_prompt', lang)
    keyboard = [[InlineKeyboardButton(get_text('cancel_button', lang), callback_data="kiok_review")]]
    
    message = await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['approval_message_id'] = message.message_id
    return AWAITING_KIOK_INSPECTION_NUM

async def process_kiok_inspection_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает номер проверки от КИОК"""
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)  # ASYNC
    inspection_number = update.message.text.strip()
    
    report_id = context.user_data.get('approving_report_id')
    if not report_id:
        return
    
    await update.message.delete()
    
    message_id = context.user_data.get('approval_message_id')
    if message_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        except:
            pass
    
    success = await WorkflowService.kiok_approve(report_id, user_id, inspection_number)  # ASYNC
    
    if success:
        await NotificationService.notify_supervisor_status_change(
            context, report_id, 'approved', user_id
        )
        
        text = get_text('kiok_approval_success', lang).format(
            report_id=report_id, 
            inspection_number=inspection_number
        )
    else:
        text = get_text('kiok_approval_error', lang)
    
    keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="kiok_review")]]
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data.pop('approving_report_id', None)
    context.user_data.pop('approval_message_id', None)
    return ConversationHandler.END

async def kiok_reject_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает причину и документы для отклонения КИОК"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    lang = await get_user_language(user_id)  # ASYNC
    report_id = int(query.data.split('_')[-1])
    
    context.user_data['rejecting_report_id'] = report_id
    context.user_data['rejecting_role'] = 'kiok'
    
    text = get_text('kiok_rejection_reason_prompt', lang)
    keyboard = [[InlineKeyboardButton(get_text('cancel_button', lang), callback_data="kiok_review")]]
    
    message = await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data['rejection_message_id'] = message.message_id
    return AWAITING_KIOK_REJECTION

async def process_kiok_rejection_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает причину отклонения от КИОК"""
    user_id = str(update.effective_user.id)
    lang = await get_user_language(user_id)  # ASYNC
    reason = update.message.text
    
    report_id = context.user_data.get('rejecting_report_id')
    if not report_id:
        return
    
    await update.message.delete()
    
    message_id = context.user_data.get('rejection_message_id')
    if message_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
        except:
            pass
    
    success = await WorkflowService.kiok_reject(report_id, user_id, reason)  # ASYNC
    
    if success:
        await NotificationService.notify_supervisor_status_change(
            context, report_id, 'rejected', user_id, reason
        )
        
        text = get_text('kiok_rejection_success', lang).format(report_id=report_id)
    else:
        text = get_text('kiok_rejection_error', lang)
    
    keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data="kiok_review")]]
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    context.user_data.pop('rejecting_report_id', None)
    context.user_data.pop('rejecting_role', None)
    context.user_data.pop('rejection_message_id', None)
    return ConversationHandler.END

async def cancel_rejection_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена процесса ввода причины/номера."""
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop('rejecting_report_id', None)
    context.user_data.pop('rejecting_role', None)
    context.user_data.pop('rejection_message_id', None)
    context.user_data.pop('approving_report_id', None)
    context.user_data.pop('approval_message_id', None)
    
    if "master" in query.data:
        await show_master_approval_menu(update, context)
    elif "kiok" in query.data:
        await show_kiok_review_menu(update, context)
        
    return ConversationHandler.END

def create_rejection_conversation():
    """Создает ConversationHandler для ввода причин отклонения и номеров проверки."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(master_reject_report_prompt, pattern="^master_reject_\\d+$"),
            CallbackQueryHandler(kiok_approve_prompt, pattern="^kiok_approve_final_"),
            CallbackQueryHandler(kiok_reject_prompt, pattern="^kiok_reject_final_"),
        ],
        states={
            AWAITING_MASTER_REJECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_master_rejection_reason)],
            AWAITING_KIOK_INSPECTION_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_kiok_inspection_number)],
            AWAITING_KIOK_REJECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_kiok_rejection_reason)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_rejection_flow, pattern="^approve_reports$"),
            CallbackQueryHandler(cancel_rejection_flow, pattern="^kiok_review$"),
        ],
        per_user=True,
        allow_reentry=True,
        name="rejection_conversation"
    )

def register_workflow_handlers(application):
    """Регистрация workflow handlers"""
    application.add_handler(CallbackQueryHandler(show_master_approval_menu, pattern="^approve_reports$"))
    application.add_handler(CallbackQueryHandler(show_master_report_details, pattern="^master_view_"))
    application.add_handler(CallbackQueryHandler(master_approve_report, pattern="^master_approve_\\d+$"))

    application.add_handler(CallbackQueryHandler(show_kiok_review_menu, pattern="^kiok_review$"))
    application.add_handler(CallbackQueryHandler(show_kiok_report_details, pattern="^kiok_view_"))
    
    logger.info("✅ Workflow handlers зарегистрированы")