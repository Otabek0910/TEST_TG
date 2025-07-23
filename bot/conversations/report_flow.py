"""
ConversationHandler для создания отчетов супервайзерами
"""

import json
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler, CallbackQueryHandler, MessageHandler, 
    filters, ContextTypes
)

from telegram.constants import ParseMode
from services.workflow_service import WorkflowService
from services.notification_service import NotificationService

from utils.constants import (
    SELECTING_BRIGADE, GETTING_CORPUS_NEW, GETTING_WORK_TYPE_NEW,
    GETTING_PIPE_DATA, CONFIRM_REPORT_NEW
)
from utils.localization import get_user_language
from database.queries import db_query
from ..middleware.security import check_user_role

logger = logging.getLogger(__name__)

# Переопределяем константы для удобства
GETTING_CORPUS = GETTING_CORPUS_NEW
GETTING_WORK_TYPE = GETTING_WORK_TYPE_NEW  
CONFIRM_REPORT = CONFIRM_REPORT_NEW
ITEMS_PER_PAGE = 8

# --- > НОВАЯ ФУНКЦИЯ ДЛЯ ПАГИНАЦИИ <---
def create_paginated_keyboard(items: list[tuple[int, str]], page: int = 0, item_prefix: str = "") -> InlineKeyboardMarkup:
    """Создает клавиатуру с пагинацией из списка кортежей (id, name)."""
    start_index = page * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    page_items = items[start_index:end_index]

    # В тексте кнопки - имя, в callback_data - ID
    keyboard = [[InlineKeyboardButton(name, callback_data=f"{item_prefix}{item_id}")] for item_id, name in page_items]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page - 1}"))
    if end_index < len(items):
        nav_buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"page_{page + 1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_report")])
    return InlineKeyboardMarkup(keyboard)

# ===== ENTRY POINT =====
async def start_report_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало создания отчета супервайзером"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(update.effective_user.id)
    user_role = await check_user_role(user_id)
    
    if not user_role.get('isSupervisor'):
        await query.answer("❌ Создание отчетов доступно только супервайзерам", show_alert=True)
        return ConversationHandler.END
    
    try:
        # # CHANGED: Запрос исправлен на использование discipline_id
        supervisor_info = await db_query(
            "SELECT brigade_ids, discipline_id FROM supervisors WHERE user_id = %s",
            (user_id,)
        )
        if not supervisor_info:
            await query.edit_message_text("❌ Информация о супервайзере не найдена.")
            return ConversationHandler.END
        
        assigned_brigades = supervisor_info[0][0] or []
        discipline_id = supervisor_info[0][1]
        
        context.user_data['supervisor_discipline_id'] = discipline_id
        
    except Exception as e:
        logger.error(f"Ошибка получения данных супервайзера {user_id}: {e}")
        await query.edit_message_text("❌ Ошибка загрузки данных.")
        return ConversationHandler.END
    
    if not assigned_brigades:
        await query.edit_message_text("❌ За вами не закреплены бригады.")
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton(f"👥 {b}", callback_data=f"select_brigade_{b}")] for b in assigned_brigades]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_report")])
    
    await query.edit_message_text(
        "👥 **Выберите бригаду для создания отчета:**",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    
    return SELECTING_BRIGADE

# ===== ВЫБОР БРИГАДЫ =====
async def select_brigade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор бригады"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем название бригады
    brigade_name = query.data.replace('select_brigade_', '')
    context.user_data['report_data'] = {'selected_brigade': brigade_name}
    
    # Переходим к выбору корпуса
    return await show_corpus_selection(update, context)

# ===== ВЫБОР КОРПУСА =====
async def show_corpus_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показывает список корпусов с пагинацией, используя ID."""
    query = update.callback_query
    
    # Теперь запрашиваем и ID, и имя
    corpus_results = await db_query("SELECT id, name FROM construction_objects ORDER BY display_order, name")
    if not corpus_results:
        await query.edit_message_text("❌ Не найдены объекты строительства в базе данных.")
        return ConversationHandler.END

    # corpus_list теперь список кортежей: [(1, 'Корпус 1'), (2, 'Корпус 2')]
    context.user_data['corpus_list'] = corpus_results 

    keyboard = create_paginated_keyboard(corpus_results, page, item_prefix="select_corpus_")
    text = "🏢 <b>Выберите корпус/объект:</b>"
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return GETTING_CORPUS

async def handle_corpus_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатия на кнопки 'Вперед' и 'Назад'."""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split('_')[1])
    
    corpus_list = context.user_data.get('corpus_list', [])
    if not corpus_list:
        return await show_corpus_selection(update, context, 0)

    keyboard = create_paginated_keyboard(corpus_list, page, item_prefix="select_corpus_")
    await query.edit_message_text("🏢 <b>Выберите корпус/объект:</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)
    
    return GETTING_CORPUS

async def select_corpus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора корпуса по ID."""
    query = update.callback_query
    await query.answer()
    
    # Получаем ID из callback_data
    corpus_id = query.data.replace('select_corpus_', '')
    
    # Находим имя корпуса по его ID
    corpus_info = await db_query("SELECT name FROM construction_objects WHERE id = %s", (corpus_id,))
    if not corpus_info:
        await query.edit_message_text("❌ Выбранный корпус не найден.")
        return ConversationHandler.END
        
    corpus_name = corpus_info[0][0]
    
    # Сохраняем и ID, и имя в контекст
    context.user_data['report_data']['corpus_id'] = corpus_id
    context.user_data['report_data']['corpus_name'] = corpus_name
    
    # Переходим к выбору вида работ (эта логика остается прежней)
    return await show_work_types_for_discipline(update, context)

# ===== ВЫБОР ВИДА РАБОТ (ТРУБОПРОВОД) =====
async def show_work_types_for_discipline(update, context):
    """Показ видов работ для дисциплины супервайзера"""
    query = update.callback_query
    
    # Получаем discipline_id из context (сохранили в start_report_creation)
    discipline_id = context.user_data.get('supervisor_discipline_id')
    
    if not discipline_id:
        await query.edit_message_text("❌ Ошибка: не удалось определить дисциплину.")
        return ConversationHandler.END
    
    # Получаем название дисциплины для отображения
    discipline_info = await db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,))
    if not discipline_info:
        await query.edit_message_text("❌ Дисциплина не найдена.")
        return ConversationHandler.END
    
    discipline_name = discipline_info[0][0]
    
    # Получаем виды работ для дисциплины
    work_types = db_query(
        "SELECT id, name, unit_of_measure FROM work_types WHERE discipline_id = %s ORDER BY display_order, name",
        (discipline_id,)
    )
    
    if not work_types:
        await query.edit_message_text(f"❌ Виды работ для дисциплины '{discipline_name}' не найдены.")
        return ConversationHandler.END
    
    text = f"🔧 **Выберите вид работ ({discipline_name}):**"
    keyboard = []
    
    for work_id, work_name, unit in work_types:
        unit_text = f" ({unit})" if unit else ""
        keyboard.append([InlineKeyboardButton(f"{work_name}{unit_text}", callback_data=f"select_work_{work_id}")])
    
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel_report")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    return GETTING_WORK_TYPE

async def select_work_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор вида работ"""
    query = update.callback_query
    await query.answer()
    
    work_id = query.data.replace('select_work_', '')
    
    # Получаем информацию о виде работ
    work_info = await db_query("SELECT name, unit_of_measure, norm_per_unit FROM work_types WHERE id = %s", (work_id,))
    if not work_info:
        await query.edit_message_text("❌ Вид работ не найден.")
        return ConversationHandler.END
    
    work_name, unit, norm = work_info[0]
    
    context.user_data['report_data'].update({
        'work_type_id': work_id,
        'work_type_name': work_name,
        'unit_of_measure': unit,
        'norm_per_unit': norm or 1.0
    })
    
    # Переходим к заполнению данных трубопровода
    return await show_pipe_data_form(update, context)

# ===== ФОРМА ДАННЫХ ТРУБОПРОВОДА =====
async def show_pipe_data_form(update, context):
    """Показ формы для ввода данных по трубопроводу"""
    query = update.callback_query
    
    report_data = context.user_data['report_data']
    
    form_text = (
        f"📋 **Заполнение отчета**\n\n"
        f"👥 Бригада: {report_data['selected_brigade']}\n"
        f"🏗️ Корпус: {report_data['corpus_name']}\n"
        f"🔧 Работы: {report_data['work_type_name']}\n\n"
        f"📝 **Введите данные через запятую:**\n"
        f"1. Диаметр трубы (мм)\n"
        f"2. Длина участка (м)\n"
        f"3. Количество сварщиков\n"
        f"4. Количество монтажников\n"
        f"5. Примечание (необязательно)\n\n"
        f"**Пример:** 100, 50.5, 2, 3, Без замечаний"
    )
    
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_report")]]
    
    await query.edit_message_text(form_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    return GETTING_PIPE_DATA

async def process_pipe_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенных данных трубопровода"""
    user_input = update.message.text.strip()
    
    # Удаляем сообщение пользователя
    await update.message.delete()
    
    try:
        # Парсим данные
        parts = [part.strip() for part in user_input.split(',')]
        
        if len(parts) < 4:
            await update.message.reply_text(
                "❌ Недостаточно данных. Введите минимум 4 значения через запятую.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_report")]])
            )
            return GETTING_PIPE_DATA
        
        diameter = float(parts[0])
        length = float(parts[1])
        welders_count = int(parts[2])
        fitters_count = int(parts[3])
        notes = parts[4] if len(parts) > 4 else ""
        
        # Сохраняем данные
        context.user_data['report_data'].update({
            'pipe_diameter': diameter,
            'pipe_length': length,
            'welders_count': welders_count,
            'fitters_count': fitters_count,
            'total_people': welders_count + fitters_count,
            'notes': notes,
            'report_date': date.today().strftime('%Y-%m-%d')
        })
        
        # Переходим к подтверждению
        return await show_report_confirmation(update, context)
        
    except (ValueError, IndexError) as e:
        await update.message.reply_text(
            "❌ Неверный формат данных. Проверьте правильность ввода.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel_report")]])
        )
        return GETTING_PIPE_DATA

# ===== ПОДТВЕРЖДЕНИЕ =====
async def show_report_confirmation(update, context):
    """Показ отчета для подтверждения"""
    report_data = context.user_data['report_data']
    
    confirmation_text = (
        f"✅ **Подтверждение отчета**\n\n"
        f"👥 Бригада: {report_data['selected_brigade']}\n"
        f"🏗️ Корпус: {report_data['corpus_name']}\n"
        f"🔧 Работы: {report_data['work_type_name']}\n"
        f"📏 Диаметр: {report_data['pipe_diameter']} мм\n"
        f"📐 Длина: {report_data['pipe_length']} м\n"
        f"👨‍🔧 Сварщики: {report_data['welders_count']} чел.\n"
        f"🔧 Монтажники: {report_data['fitters_count']} чел.\n"
        f"👥 Всего: {report_data['total_people']} чел.\n"
        f"📅 Дата: {report_data['report_date']}\n"
    )
    
    if report_data.get('notes'):
        confirmation_text += f"📝 Примечание: {report_data['notes']}\n"
    
    confirmation_text += "\n**Отправить отчет?**"
    
    keyboard = [
        [InlineKeyboardButton("✅ Отправить", callback_data="submit_report")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_report")]
    ]
    
    await update.message.reply_text(confirmation_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    return CONFIRM_REPORT

async def submit_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправка отчета в БД с учетом новой структуры и workflow"""
    query = update.callback_query
    await query.answer("Сохраняю отчет...")
    
    user_id = str(update.effective_user.id)
    report_data = context.user_data.get('report_data', {})

    if not report_data:
        await query.edit_message_text("❌ Ошибка: данные отчета утеряны.")
        context.user_data.clear()
        return ConversationHandler.END

    try:
        # # CHANGED: Получаем discipline_id напрямую из контекста
        discipline_id = context.user_data.get('supervisor_discipline_id')
        if not discipline_id:
            await query.edit_message_text("❌ Ошибка: не удалось определить дисциплину.")
            return ConversationHandler.END
        
        # Формируем данные для сохранения
        details_for_json = {
            'pipe_diameter': report_data.get('pipe_diameter'),
            'pipe_length': report_data.get('pipe_length'),
            'welders_count': report_data.get('welders_count'),
            'fitters_count': report_data.get('fitters_count')
        }
        
        report_payload = {
            'report_date': report_data.get('report_date'),
            'brigade_name': report_data.get('selected_brigade'),
            'corpus_name': report_data.get('corpus_name'),
            'work_type_name': report_data.get('work_type_name'),
            'details': { 'pipe_diameter': report_data.get('pipe_diameter') } # Пример
        }
        
        # # CHANGED: Вызываем обновленный метод WorkflowService
        report_id = await WorkflowService.create_report(
            supervisor_id=user_id,
            discipline_id=discipline_id,
            report_data=report_payload
        )
        
        if report_id:
            try:
                # 1. Получаем имя дисциплины по ее ID
                discipline_name_result = await db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,))
                
                if discipline_name_result:
                    discipline_name = discipline_name_result[0][0]
                    
                    # 2. Вызываем СУЩЕСТВУЮЩУЮ функцию с ИМЕНЕМ дисциплины
                    masters = await NotificationService.get_users_for_discipline_notification(discipline_name, 'master')
                    
                    for master_id in masters:
                        await NotificationService.notify_master_new_report(context, report_id, master_id)
                    
                    logger.info(f"Уведомления о новом отчете {report_id} отправлены {len(masters)} мастерам")
                else:
                    logger.warning(f"Не удалось найти имя дисциплины для ID {discipline_id}, уведомления не отправлены.")

            except Exception as e:
                logger.error(f"Ошибка отправки уведомлений мастерам: {e}")
            
            success_text = f"✅ **Отчет создан!**\nID: {report_id}\nОтправлен мастеру на подтверждение."
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")]]
            await query.edit_message_text(success_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            
        else:
            await query.edit_message_text("❌ Ошибка при сохранении отчета в БД.")
            
    except Exception as e:
        logger.error(f"Критическая ошибка при создании отчета: {e}")
        await query.edit_message_text("❌ Произошла критическая ошибка при создании отчета.")
    
    context.user_data.clear()
    return ConversationHandler.END

# ===== ОТМЕНА =====
async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена создания отчета"""
    query = update.callback_query
    await query.answer("❌ Создание отчета отменено")
    
    from ..handlers.common import back_to_start
    await back_to_start(update, context)
    
    context.user_data.clear()
    return ConversationHandler.END

# ===== СОЗДАНИЕ CONVERSATION HANDLER =====
def create_report_conversation():
    """Создание ConversationHandler для создания отчетов"""
    # Этот код остается без изменений
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_report_creation, pattern="^new_report$")],
        states={
            SELECTING_BRIGADE: [CallbackQueryHandler(select_brigade, pattern="^select_brigade_")],
            GETTING_CORPUS: [
                # Сначала проверяем, не кнопка ли это пагинации
                CallbackQueryHandler(handle_corpus_pagination, pattern="^page_"),
                # Если нет - значит, это выбор корпуса
                CallbackQueryHandler(select_corpus, pattern="^select_corpus_")
            ],
            GETTING_WORK_TYPE: [CallbackQueryHandler(select_work_type, pattern="^select_work_")],
            GETTING_PIPE_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_pipe_data)],
            CONFIRM_REPORT: [CallbackQueryHandler(submit_report, pattern="^submit_report$")]
        },
        fallbacks=[CallbackQueryHandler(cancel_report, pattern="^cancel_report$")],
        per_user=True, allow_reentry=True, name="report_conversation"
    )
