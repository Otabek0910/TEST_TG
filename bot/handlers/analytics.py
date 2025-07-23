# bot/handlers/analytics.py

import logging
from datetime import date, datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler, filters

from bot.middleware.security import check_user_role
from services.analytics_service import AnalyticsService
from utils.localization import get_user_language, get_text, get_data_translation
from utils.constants import SELECTING_OVERVIEW_ACTION, AWAITING_OVERVIEW_DATE, GETTING_HR_DATE
from database.queries import db_query

logger = logging.getLogger(__name__)


async def show_historical_report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню исторических отчетов (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = get_user_language(user_id)
    
    await query.edit_message_text(f"⏳ {get_text('loading_please_wait', lang)}...", parse_mode=ParseMode.MARKDOWN)
    
    if user_role.get('isAdmin') or user_role.get('managerLevel') == 1:
        stats_data = await AnalyticsService.get_overall_statistics() # FIXED: await
        
        if not stats_data:
            await query.edit_message_text("❌ Ошибка при получении статистики.")
            return
            
        # Формируем текст сообщения
        header = "📊 *Общая сводка по всем дисциплинам*"
        report_stats = stats_data.get('report_stats', {})
        total_reports = stats_data.get('total_reports', 0)
        non_reporters_count = stats_data.get('non_reporters_count', 0)
        
        discipline_analysis = stats_data.get('discipline_analysis', {})
        overall_output_percent = discipline_analysis.get('overall_output_percent', 0)
        discipline_summary = discipline_analysis.get('discipline_summary', [])
        
        message_parts = [
            header,
            "---",
            f"📈 *Статистика отчетов (за все время):*",
            f"  - Всего подано: *{total_reports}*",
            f"  - ✅ Согласовано: *{report_stats.get('1', 0)}*", 
            f"  - ❌ Отклонено: *{report_stats.get('-1', 0)}*",
            f"  - ⏳ Ожидает: *{report_stats.get('0', 0)}*",
            f"\n🚫 *Не сдали отчет сегодня: {non_reporters_count} бригад*",
            f"\n💡 *Общая средняя выработка: {overall_output_percent:.1f}%*"
        ]
        
        if discipline_summary:
            message_parts.append("\n📊 *Средняя выработка по дисциплинам:*")
            for disc in discipline_summary:
                translated_name = get_data_translation(disc['name'], lang)
                message_parts.append(f"  - *{translated_name}*: средняя выработка *{disc['avg_output']:.1f}%*")
        
        message_parts.append("\n\n🗂️ *Выберите дисциплину для детального отчета:*")
        
        final_text = "\n".join(message_parts)
        
        # Кнопки дисциплин
        disciplines = await db_query("SELECT name FROM disciplines ORDER BY name") # FIXED: await
        keyboard_buttons = []
        
        if disciplines:
            for name, in disciplines:
                translated_discipline = get_data_translation(name, lang)
                button_text = f"📋 {translated_discipline}"
                keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=f"gen_hist_report_{name}")])
        
        keyboard_buttons.append([InlineKeyboardButton(get_text('back_button', lang), callback_data="report_menu_all")])
        
        await query.edit_message_text(
            text=final_text, 
            reply_markup=InlineKeyboardMarkup(keyboard_buttons), 
            parse_mode=ParseMode.MARKDOWN
        )
        
    else:
        # Для других ролей показываем их дисциплину
        discipline = user_role.get('discipline')
        if not discipline:
            await query.edit_message_text("❗️*Ошибка:* Для вашей роли не задана дисциплина.")
            return
        await generate_discipline_dashboard(update, context, discipline_name=discipline)


async def generate_discipline_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, discipline_name: str = None):
    """Генерация дашборда по дисциплине (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    # Извлекаем название дисциплины из callback_data если не передано
    if not discipline_name:
        if "gen_hist_report_" in query.data:
            discipline_name = query.data.replace('gen_hist_report_', '')
        else:
            discipline_name = query.data.split('_', 3)[-1]
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = get_user_language(user_id)
    
    await query.edit_message_text(
        f"⏳ {get_text('loading_please_wait', lang)} ({get_data_translation(discipline_name, lang)})...", 
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Получаем данные через сервис
    dashboard_data = await AnalyticsService.get_discipline_dashboard_data(discipline_name, user_role) # FIXED: await
    
    if not dashboard_data:
        await query.edit_message_text("❌ Ошибка при получении данных дашборда.")
        return
    
    # Формируем текст сообщения
    translated_discipline = get_data_translation(discipline_name, lang)
    header = f"📊 *Подробный отчет по дисциплине «{translated_discipline}»*"
    
    user_counts = dashboard_data.get('user_counts', {})
    report_stats = dashboard_data.get('report_stats', {})
    total_reports = dashboard_data.get('total_reports', 0)
    non_reporters_count = dashboard_data.get('non_reporters_count', 0)
    low_performance_count = dashboard_data.get('low_performance_count', 0)
    analysis_data = dashboard_data.get('analysis_data', {})
    
    message_parts = [
        header,
        "---",
        f"👤 *Пользователи в дисциплине:*",
        f"  - Бригадиры: *{user_counts['brigades']}*", 
        f"  - ПТО: *{user_counts['pto']}*",
        f"  - КИОК: *{user_counts['kiok']}*",
        f"\n📈 *Общая статистика по дисциплине:*",
        f"  - Всего подано: *{total_reports}*",
        f"  - ✅ Согласовано: *{report_stats.get('1', 0)}*",
        f"  - ❌ Отклонено: *{report_stats.get('-1', 0)}*", 
        f"  - ⏳ Ожидает: *{report_stats.get('0', 0)}*",
        f"\n🚫 *Не сдали отчет сегодня: {non_reporters_count} бригад*"
    ]
    
    # Добавляем данные о проблемных бригадах
    if low_performance_count > 0:
        message_parts.append(f"⚠️ *Бригад с низкой выработкой: {low_performance_count}*")
    
    # Добавляем анализ выработки (если есть)
    if analysis_data and not user_role.get('isKiok'):
        overall_output = analysis_data.get('overall_output_percent', 0)
        work_analysis = analysis_data.get('work_analysis', [])
        
        message_parts.append(f"\n💡 *Общая средняя выработка: {overall_output:.1f}%*")
        
        if work_analysis:
            message_parts.append("\n🛠️ *Анализ по видам работ (факт/план | % выработки):*")
            for work in work_analysis:
                work_name = get_data_translation(work['work_type'], lang)
                total_volume = work['total_volume']
                total_planned = work['total_planned'] 
                avg_output = work['avg_output']
                message_parts.append(f"  - *{work_name}*:")
                message_parts.append(f"    `{total_volume:.1f} / {total_planned:.1f} | {avg_output:.1f}%`")
    
    final_text = "\n".join(message_parts)
    
    # Кнопка "Назад"
    back_button_callback = "report_historical" if (user_role.get('isAdmin') or user_role.get('managerLevel') == 1) else "report_menu_all"
    keyboard = [[InlineKeyboardButton(get_text('back_button', lang), callback_data=back_button_callback)]]
    
    await query.edit_message_text(
        text=final_text, 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.MARKDOWN
    )


async def show_overview_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_date_override: date = None) -> int:
    """Показать обзорный дашборд (адаптировано из старого кода)"""
    query = update.callback_query
    
    # Определяем дату
    selected_date = date.today()
    if selected_date_override:
        selected_date = selected_date_override
    elif query:
        await query.answer()
        if query.data.startswith("report_overview_date_"):
            date_str = query.data.split('_')[-1]
            if date_str == 'today':
                selected_date = date.today()
            elif date_str == 'yesterday':
                selected_date = date.today() - timedelta(days=1)
            else:
                try:
                    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    selected_date = date.today()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = get_user_language(user_id)
    
    # Показываем индикатор загрузки
    if query.message:
        wait_msg = await query.edit_message_text(f"⏳ {get_text('loading_please_wait', lang)}")
    else:
        wait_msg = await update.message.reply_text(f"⏳ {get_text('loading_please_wait', lang)}")
    
    # Получаем данные через сервис
    dashboard_data = await AnalyticsService.get_overview_dashboard_data(selected_date) # FIXED: await
    discipline_data = dashboard_data.get('discipline_data', [])
 
    # Формируем сообщение
    date_str_for_callback = selected_date.strftime('%Y-%m-%d')
    message_lines = [f"📊 *Сводка за {selected_date.strftime('%d.%m.%Y')}*", ""]
    
    if not discipline_data:
        message_lines.append("📋 *На выбранную дату нет данных*")
    else:
        for disc in discipline_data:
            disc_name = get_data_translation(disc['name'], lang)
            main_people = disc['main_people']
            other_people = disc['other_people'] 
            performance = disc['performance']
            fact_volume = disc['fact_volume']
            
            fact_volume_str = f"({fact_volume:.1f})" if fact_volume > 0 else ""
            
            if main_people > 0:
                message_lines.append(f"*{disc_name}:* {main_people} чел. * ({performance:.1f}%) {fact_volume_str}")
            
            if other_people > 0:
                message_lines.append(f"_{get_text('other_works_label', lang)}:_ *{other_people} чел.*")
    
    message_text = "\n".join(message_lines)
    
    # Кнопки даты
    date_buttons = [
        InlineKeyboardButton("Вчера", callback_data="report_overview_date_yesterday"),
        InlineKeyboardButton("Сегодня", callback_data="report_overview_date_today"), 
        InlineKeyboardButton("Выбрать дату", callback_data="report_overview_pick_date")
    ]
    
    keyboard_buttons = [date_buttons]
    
    # Кнопки графиков по ролям
    if user_role.get('isAdmin') or user_role.get('managerLevel') == 1:
        disciplines = await db_query("SELECT id, name FROM disciplines ORDER BY name") # FIXED: await
        if disciplines:
            for disc_id, disc_name in disciplines:
                translated_name = get_data_translation(disc_name, lang)
                keyboard_buttons.append([InlineKeyboardButton(
                    f"📊 {translated_name}", 
                    callback_data=f"gen_overview_chart_{disc_id}_{date_str_for_callback}"
                )])
    
    elif user_role.get('isPto') or user_role.get('managerLevel') == 2:
        user_discipline_name = user_role.get('discipline')
        if user_discipline_name:
            discipline_id_raw = await db_query("SELECT id FROM disciplines WHERE name = %s", (user_discipline_name,)) # FIXED: await
            if discipline_id_raw:
                user_discipline_id = discipline_id_raw[0][0]
                keyboard_buttons.append([InlineKeyboardButton(
                    "📊 Показать мой график", 
                    callback_data=f"gen_overview_chart_{user_discipline_id}_{date_str_for_callback}"
                )])
    
    keyboard_buttons.append([InlineKeyboardButton("◀️ Назад в меню отчетов", callback_data="report_menu_all")])
    
    await wait_msg.edit_text(
        text=message_text, 
        reply_markup=InlineKeyboardMarkup(keyboard_buttons), 
        parse_mode=ParseMode.MARKDOWN
    )
    
    return SELECTING_OVERVIEW_ACTION

  
async def prompt_for_overview_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос даты для обзорного дашборда"""
    query = update.callback_query
    await query.answer()
    
    lang = get_user_language(str(query.from_user.id))
    
    await query.edit_message_text(
        text=get_text('prompt_overview_date', lang),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(get_text('back_button', lang), callback_data="report_overview")
        ]]),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return AWAITING_OVERVIEW_DATE


async def process_overview_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка введенной даты для обзорного дашборда"""
    user_input = update.message.text.strip()
    lang = get_user_language(str(update.effective_user.id))
    
    try:
        # Пробуем разные форматы даты
        for date_format in ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
            try:
                selected_date = datetime.strptime(user_input, date_format).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError("Неподдерживаемый формат даты")
        
        # Проверяем разумные границы
        if selected_date > date.today():
            await update.message.reply_text(
                get_text('date_future_error', lang),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(get_text('back_button', lang), callback_data="report_overview")
                ]])
            )
            return AWAITING_OVERVIEW_DATE
        
        if selected_date < date.today() - timedelta(days=365):
            await update.message.reply_text(
                get_text('date_too_old_error', lang),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(get_text('back_button', lang), callback_data="report_overview")
                ]])
            )
            return AWAITING_OVERVIEW_DATE
        
        # Переходим к показу дашборда с выбранной датой
        return await show_overview_dashboard_menu(update, context, selected_date_override=selected_date)
        
    except ValueError:
        await update.message.reply_text(
            get_text('date_format_error', lang),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(get_text('back_button', lang), callback_data="report_overview")
            ]])
        )
        return AWAITING_OVERVIEW_DATE


async def generate_overview_chart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Генерация графика по дисциплине (адаптировано из старого кода)"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    lang = get_user_language(user_id)
    
    try:
        # Парсим callback_data
        base_callback, date_str = query.data.rsplit('_', 1)
        discipline_id = int(base_callback.split('_')[-1])
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, IndexError):
        logger.error(f"Ошибка разбора callback_data в generate_overview_chart: {query.data}")
        await query.edit_message_text("❌ Произошла внутренняя ошибка. Не удалось разобрать данные для графика.")
        return SELECTING_OVERVIEW_ACTION
    
    await query.edit_message_text(f"⏳ {get_text('loading_please_wait', lang)}")
    
    # Получаем данные для графика через сервис
    chart_data = await AnalyticsService.get_chart_data(discipline_id, selected_date) # FIXED: await
  
    if not chart_data:
        discipline_name_raw = await db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,)) # FIXED: await
        discipline_name = discipline_name_raw[0][0] if discipline_name_raw else "Неизвестная"
        
        await query.edit_message_text(
            f"Нет данных для построения графика\n\n"
            f"По дисциплине «{discipline_name}» за выбранный период нет отчетов с нормируемыми работами.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data=f"report_overview_date_{date_str}")
            ]])
        )
        return SELECTING_OVERVIEW_ACTION
    
    # Формируем текстовый график (без matplotlib пока)
    discipline_name = chart_data['discipline_name']
    chart_items = chart_data['chart_data']
    
    message_lines = [
        f"📊 *График по дисциплине «{get_data_translation(discipline_name, lang)}»*",
        f"📅 *Дата: {selected_date.strftime('%d.%m.%Y')}*",
        "",
        "*План vs Факт по видам работ:*",
        ""
    ]
    
    for item in chart_items:
        work_type = get_data_translation(item['work_type'], lang)
        plan = item['plan']
        fact = item['fact']
        people = item['people']
        percentage = (fact / plan * 100) if plan > 0 else 0
        
        message_lines.append(f"*{work_type}* ({people} чел.):")
        message_lines.append(f"  План: {plan:.1f}")
        message_lines.append(f"  Факт: {fact:.1f} ({percentage:.1f}%)")
        message_lines.append("")
    
    message_text = "\n".join(message_lines)
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"report_overview_date_{date_str}")]]
    
    await query.edit_message_text(
        text=message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return SELECTING_OVERVIEW_ACTION


async def show_hr_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню 'Людские ресурсы' с выбором дисциплин"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = get_user_language(user_id)
    
    # Проверяем права доступа
    if not (user_role.get('isAdmin') or user_role.get('isManager') or user_role.get('isPto')):
        await query.edit_message_text("⛔️ У вас нет прав для просмотра HR отчетов.")
        return
    
    # Получаем дисциплины для выбора
    if user_role.get('isAdmin') or user_role.get('managerLevel') == 1:
        disciplines = await db_query("SELECT id, name FROM disciplines ORDER BY name") # FIXED: await
    else:
        user_discipline = user_role.get('discipline')
        disciplines = await db_query("SELECT id, name FROM disciplines WHERE name = %s", (user_discipline,)) # FIXED: await
 
    if not disciplines:
        await query.edit_message_text("❌ Дисциплины не найдены.")
        return
    
    keyboard_buttons = []
    for disc_id, disc_name in disciplines:
        translated_name = get_data_translation(disc_name, lang)
        keyboard_buttons.append([InlineKeyboardButton(
            f"👥 {translated_name}", 
            callback_data=f"hr_date_select_{disc_id}"
        )])
    
    keyboard_buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="report_menu_all")])
    
    text = "👥 **Людские ресурсы**\n\nВыберите дисциплину для просмотра состава персонала:"
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard_buttons),
        parse_mode=ParseMode.MARKDOWN
    )


async def get_hr_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает дату для HR отчета"""
    query = update.callback_query
    await query.answer()
    
    # Парсим discipline_id из callback
    discipline_id = query.data.replace('hr_date_select_', '')
    context.user_data['hr_discipline_id'] = discipline_id
    
    lang = get_user_language(str(query.from_user.id))
    
    # Получаем название дисциплины
    disc_name_raw = await db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,)) # FIXED: await
    disc_name = disc_name_raw[0][0] if disc_name_raw else "Неизвестная"
    translated_name = get_data_translation(disc_name, lang)
    
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data=f"hr_report_today_{discipline_id}")],
        [InlineKeyboardButton("Вчера", callback_data=f"hr_report_yesterday_{discipline_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="show_hr_menu")]
    ]
    
    text = (
        f"📅 **Дата для отчета по дисциплине «{translated_name}»**\n\n"
        f"Выберите дату или введите в формате ДД.ММ.ГГГГ:"
    )
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return GETTING_HR_DATE

  
async def process_hr_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает введенную дату для HR отчета"""
    user_input = update.message.text.strip()
    discipline_id = context.user_data.get('hr_discipline_id')
    
    if not discipline_id:
        await update.message.reply_text("❌ Ошибка: дисциплина не выбрана.")
        return ConversationHandler.END
    
    try:
        selected_date = datetime.strptime(user_input, "%d.%m.%Y").date()
        await show_hr_report_for_date(update, context, discipline_id, selected_date)
    except ValueError:
        lang = get_user_language(str(update.effective_user.id))
        await update.message.reply_text(
            "❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например: 15.01.2025)",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Назад", callback_data="show_hr_menu")
            ]])
        )
        return GETTING_HR_DATE
    
    context.user_data.clear()
    return ConversationHandler.END


async def show_hr_report_for_date(update, context, discipline_id, selected_date: date):
    """Показывает HR отчет за конкретную дату"""
    
    try:
        # Получаем данные через сервис аналитики
        hr_data = await AnalyticsService.get_hr_report_data(discipline_id, selected_date)
        
        if not hr_data:
            text = f"📋 За {selected_date.strftime('%d.%m.%Y')} нет данных по табелям"
        else:
            # Формируем отчет
            disc_name = hr_data.get('discipline_name', 'Неизвестная')
            roster_data = hr_data.get('roster_data', [])
            total_people = hr_data.get('total_people', 0)
            brigades_count = hr_data.get('brigades_count', 0)
            
            message_lines = [
                f"👥 **HR отчет по дисциплине «{disc_name}»**",
                f"📅 **Дата:** {selected_date.strftime('%d.%m.%Y')}",
                "",
                f"▪️ **Всего заявлено:** {total_people} чел.",
                f"▪️ **Активных бригад:** {brigades_count}",
                ""
            ]
            
            if roster_data:
                message_lines.append("**Состав по должностям:**")
                for role, count in roster_data:
                    message_lines.append(f"  - {role}: **{count}** чел.")
            
            text = "\n".join(message_lines)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="show_hr_menu")]]
        
        if hasattr(update, 'message') and update.message:
            # Если пришло текстовое сообщение, отвечаем на него
            await update.message.reply_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # Если из callback query
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
    except Exception as e:
        logger.error(f"Ошибка генерации HR отчета: {e}")
        error_text = "❌ Ошибка при формировании HR отчета"
        
        if hasattr(update, 'message') and update.message:
            await update.message.reply_text(error_text)
        else:
            await update.callback_query.edit_message_text(error_text)

# === ПРОБЛЕМНЫЕ БРИГАДЫ ===

async def handle_problem_brigades_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает меню выбора даты для отчета 'Проблемные бригады'"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = get_user_language(user_id)
    
    # Проверяем права доступа
    if not (user_role.get('isAdmin') or user_role.get('isManager')):
        await query.edit_message_text("⛔️ У вас нет прав для просмотра отчета по проблемным бригадам.")
        return
    
    keyboard = [
        [InlineKeyboardButton("Сегодня", callback_data="problem_brigades_by_date_today")],
        [InlineKeyboardButton("Вчера", callback_data="problem_brigades_by_date_yesterday")],
        [InlineKeyboardButton("◀️ Назад", callback_data="report_menu_all")]
    ]
    
    await query.edit_message_text(
        text="⚠️ **Проблемные бригады**\n\nВыберите период для просмотра отчета:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def generate_problem_brigades_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Генерирует отчет по проблемным бригадам"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = get_user_language(user_id)
    
    # Определяем дату
    if "today" in query.data:
        selected_date = date.today()
    elif "yesterday" in query.data:
        selected_date = date.today() - timedelta(days=1)
    else:
        selected_date = date.today()
    
    await query.edit_message_text(f"⏳ {get_text('loading_please_wait', lang)}...")
    
    try:
        # Получаем данные через сервис
        problem_data = await AnalyticsService.get_problem_brigades_data(selected_date, user_role)
        
        if not problem_data:
            text = f"✅ На {selected_date.strftime('%d.%m.%Y')} проблемных бригад не выявлено"
        else:
            # Формируем отчет
            message_lines = [
                f"⚠️ **Проблемные бригады за {selected_date.strftime('%d.%m.%Y')}**",
                ""
            ]
            
            non_reporters = problem_data.get('non_reporters', [])
            low_performers = problem_data.get('low_performers', [])
            
            if non_reporters:
                message_lines.append("**Не сдали отчет:**")
                for brigade_info in non_reporters:
                    discipline = get_data_translation(brigade_info['discipline'], lang)
                    message_lines.append(f"  - {brigade_info['name']} ({discipline})")
                message_lines.append("")
            
            if low_performers:
                message_lines.append("**Низкая выработка (<100%):**")
                for brigade_info in low_performers:
                    discipline = get_data_translation(brigade_info['discipline'], lang)
                    performance = brigade_info['performance']
                    message_lines.append(f"  - {brigade_info['name']} ({discipline}): {performance:.1f}%")
            
            text = "\n".join(message_lines)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="handle_problem_brigades_button")]]
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка генерации отчета по проблемным бригадам: {e}")
        await query.edit_message_text("❌ Ошибка при формировании отчета")

# === ПРОИЗВОДИТЕЛЬНОСТЬ БРИГАДИРОВ ===


async def show_foreman_performance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает отчет по производительности бригадиров"""
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    user_role = check_user_role(user_id)
    lang = get_user_language(user_id)
    
    # Проверяем права доступа
    if not (user_role.get('isAdmin') or user_role.get('isManager')):
        await query.edit_message_text("⛔️ У вас нет прав для просмотра производительности бригадиров.")
        return
    
    await query.edit_message_text(f"⏳ {get_text('loading_please_wait', lang)}...")
    
    try:
        # Получаем данные за последние 7 дней
        performance_data = await AnalyticsService.get_foreman_performance_data(user_role)
        
        if not performance_data:
            text = "📊 Нет данных о производительности бригадиров"
        else:
            message_lines = [
                "📊 **Производительность бригадиров (последние 7 дней)**",
                ""
            ]
            
            for brigade_info in performance_data:
                name = brigade_info['name']
                discipline = get_data_translation(brigade_info['discipline'], lang)
                avg_performance = brigade_info['avg_performance']
                reports_count = brigade_info['reports_count']
                
                performance_icon = "🟢" if avg_performance >= 100 else "🟡" if avg_performance >= 80 else "🔴"
                
                message_lines.append(
                    f"{performance_icon} **{name}** ({discipline})\n"
                    f"    Средняя выработка: {avg_performance:.1f}% | Отчетов: {reports_count}"
                )
            
            text = "\n".join(message_lines)
        
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="report_menu_all")]]
        
        await query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения данных о производительности: {e}")
        await query.edit_message_text("❌ Ошибка при получении данных")

# === ОБНОВЛЕНИЕ register_analytics_handlers ===

def register_analytics_handlers(application):
    """Регистрация обработчиков аналитики"""
    from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ConversationHandler
    
    # ConversationHandler для обзорного дашборда
    overview_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(show_overview_dashboard_menu, pattern="^report_overview$")],
        states={
            SELECTING_OVERVIEW_ACTION: [
                CallbackQueryHandler(show_overview_dashboard_menu, pattern="^report_overview_date_"),
                CallbackQueryHandler(prompt_for_overview_date, pattern="^report_overview_pick_date$"),
                CallbackQueryHandler(generate_overview_chart, pattern="^gen_overview_chart_"),
            ],
            AWAITING_OVERVIEW_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_overview_date),
                CallbackQueryHandler(show_overview_dashboard_menu, pattern="^report_overview_date_"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(show_historical_report_menu, pattern="^report_menu_all$"),
        ],
        per_user=True, allow_reentry=True
    )

    hr_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(get_hr_date, pattern="^hr_date_select_")],
        states={
            GETTING_HR_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_hr_date)]
        },
        fallbacks=[
            CallbackQueryHandler(show_hr_menu, pattern="^show_hr_menu$"),
        ],
        per_user=True, allow_reentry=True
    )
    application.add_handler(hr_conv_handler)
    
    application.add_handler(overview_conv_handler)
    
    # Отдельные обработчики
    application.add_handler(CallbackQueryHandler(show_historical_report_menu, pattern="^report_historical$"))
    application.add_handler(CallbackQueryHandler(generate_discipline_dashboard, pattern="^gen_hist_report_"))
    
    # НОВЫЕ обработчики
    application.add_handler(CallbackQueryHandler(show_hr_menu, pattern="^show_hr_menu$"))
    application.add_handler(CallbackQueryHandler(handle_problem_brigades_button, pattern="^handle_problem_brigades_button$"))
    application.add_handler(CallbackQueryHandler(generate_problem_brigades_report, pattern="^problem_brigades_by_date_"))
    application.add_handler(CallbackQueryHandler(show_foreman_performance, pattern="^foreman_performance$"))

    # HR отчеты с быстрыми кнопками
    application.add_handler(CallbackQueryHandler(
        lambda u, c: show_hr_report_for_date(u, c, u.callback_query.data.split('_')[-1], date.today()),
        pattern="^hr_report_today_"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: show_hr_report_for_date(u, c, u.callback_query.data.split('_')[-1], date.today() - timedelta(days=1)),
        pattern="^hr_report_yesterday_"
    ))
    
    
    logger.info("✅ Analytics handlers зарегистрированы")