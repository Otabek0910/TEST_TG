"""
Сервис для отправки уведомлений и напоминаний
"""

import logging
from datetime import date, datetime
from typing import List
from telegram.ext import ContextTypes
# FIXED: Импортируем нужные константы и хелперы
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from database.queries import db_query, db_execute
from utils.localization import get_text, get_user_language

from telegram.ext import ExtBot
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)

class NotificationService:
    """Сервис для управления уведомлениями"""
    
    @staticmethod
    async def send_roster_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: str) -> bool:
        """Отправляет утреннее напоминание о подаче табеля"""
        try:
            lang = await get_user_language(user_id)
            today_str = date.today().strftime('%Y-%m-%d')
            
            # Проверяем, подан ли уже табель
            roster_check = await db_query(
                "SELECT id FROM daily_rosters WHERE brigade_user_id = %s AND roster_date = %s",
                (user_id, today_str)
            )
            
            if roster_check:
                return True  # Табель уже подан, напоминание не нужно
            
            # Получаем информацию о бригадире
            brigade_info = await db_query(
                "SELECT first_name, last_name FROM brigades WHERE user_id = %s",
                (user_id,)
            )
            
            if not brigade_info:
                return False
            
            first_name = brigade_info[0][0] or ""
            
            text = get_text('roster_morning_reminder', lang).format(
                name=first_name,
                date=date.today().strftime('%d.%m.%Y')
            )
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton(get_text('submit_roster_button', lang), callback_data="submit_roster")],
                [InlineKeyboardButton(get_text('remind_later_button', lang), callback_data="remind_later")]
            ]
            
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            # Обновляем запись о последней отправке
            await db_execute(
                "UPDATE scheduled_notifications SET last_sent = %s WHERE user_id = %s AND notification_type = 'roster_reminder'",
                (date.today(), user_id)
            )
            
            logger.info(f"Отправлено напоминание о табеле пользователю {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания о табеле: {e}")
            return False
    
    @staticmethod
    async def notify_master_new_report(context: ContextTypes.DEFAULT_TYPE, report_id: int, master_id: str) -> bool:
        """Уведомляет мастера о новом отчете для подтверждения"""
        try:
            lang = await get_user_language(master_id)
            
            report_info = await db_query("""
                SELECT r.supervisor_id, r.brigade_name, r.corpus_name, r.work_type_name, 
                       r.report_date, s.supervisor_name
                FROM reports r LEFT JOIN supervisors s ON r.supervisor_id = s.user_id WHERE r.id = %s
            """, (report_id,))
            
            if not report_info: return False
            
            supervisor_id, brigade_name, corpus_name, work_type, report_date, supervisor_name = report_info[0]
            
            # FIXED: Экранируем все переменные, которые вставляются в текст
            safe_supervisor = escape_markdown(supervisor_name or f"ID: {supervisor_id}", version=2)
            safe_brigade = escape_markdown(brigade_name, version=2)
            safe_corpus = escape_markdown(corpus_name, version=2)
            safe_work_type = escape_markdown(work_type, version=2)
            
            text = get_text('master_new_report_notification', lang).format(
                supervisor=safe_supervisor, brigade=safe_brigade, corpus=safe_corpus,
                work_type=safe_work_type, date=report_date.strftime('%d.%m.%Y'), report_id=report_id
            )
            
            keyboard = [[
                InlineKeyboardButton(get_text('view_details_button', lang), callback_data=f"master_view_{report_id}")
            ]]
            
            # FIXED: Используем ParseMode.MARKDOWN_V2
            await context.bot.send_message(
                chat_id=master_id, text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
            logger.info(f"Уведомление о новом отчете {report_id} отправлено мастеру {master_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка уведомления мастера: {e}")
            return False
    
    @staticmethod
    async def notify_kiok_new_report(context: ContextTypes.DEFAULT_TYPE, report_id: int, kiok_id: str) -> bool:
        """Уведомляет КИОК о новом отчете для проверки"""
        try:
            lang = await get_user_language(kiok_id)
            
            report_info = await db_query("""
                SELECT r.brigade_name, r.corpus_name, r.work_type_name, r.report_date, r.master_id, m.master_name
                FROM reports r LEFT JOIN masters m ON r.master_id = m.user_id WHERE r.id = %s
            """, (report_id,))
            
            if not report_info: return False
            
            brigade_name, corpus_name, work_type, report_date, master_id, master_name = report_info[0]
            
            # FIXED: Экранируем все переменные
            safe_brigade = escape_markdown(brigade_name, version=2)
            safe_corpus = escape_markdown(corpus_name, version=2)
            safe_work_type = escape_markdown(work_type, version=2)
            safe_master = escape_markdown(master_name or f"ID: {master_id}", version=2)
            
            text = get_text('kiok_new_report_notification', lang).format(
                brigade=safe_brigade, corpus=safe_corpus, work_type=safe_work_type,
                date=report_date.strftime('%d.%m.%Y'), master=safe_master, report_id=report_id
            )
            
            keyboard = [[
                InlineKeyboardButton(get_text('view_details_button', lang), callback_data=f"kiok_view_{report_id}")
            ]]
            
            await context.bot.send_message(
                chat_id=kiok_id, text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
            logger.info(f"Уведомление о новом отчете {report_id} отправлено КИОК {kiok_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка уведомления КИОК: {e}")
            return False
    
    @staticmethod
    async def notify_supervisor_status_change(context: ContextTypes.DEFAULT_TYPE, report_id: int, 
                                            new_status: str, approver_id: str, reason: str = None) -> bool:
        """Уведомляет супервайзера об изменении статуса отчета"""
        try:
            report_info = await db_query("SELECT supervisor_id, brigade_name, work_type_name, report_date FROM reports WHERE id = %s", (report_id,))
            if not report_info: return False
            
            supervisor_id, brigade_name, work_type, report_date = report_info[0]
            lang = await get_user_language(supervisor_id)
            
            text_key = {
                'approved': 'supervisor_report_approved',
                'rejected': 'supervisor_report_rejected'
            }.get(new_status, 'supervisor_report_status_changed')
            
            # FIXED: Экранируем все переменные
            safe_brigade = escape_markdown(brigade_name, version=2)
            safe_work_type = escape_markdown(work_type, version=2)
            safe_reason = escape_markdown(reason or "", version=2)
            
            text = get_text(text_key, lang).format(
                report_id=report_id, brigade=safe_brigade, work_type=safe_work_type,
                date=report_date.strftime('%d.%m.%Y'), reason=safe_reason
            )
            
            keyboard = [[InlineKeyboardButton(get_text('view_my_reports_button', lang), callback_data="my_reports")]]
            
            await context.bot.send_message(
                chat_id=supervisor_id, text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return True
            
        except Exception as e:
            logger.error(f"Ошибка уведомления супервайзера: {e}")
            return False
    
    @staticmethod
    async def setup_daily_reminders():
        """Настраивает ежедневные напоминания для всех бригадиров"""
        try:
            # Получаем всех активных бригадиров
            brigades = await db_query("SELECT user_id FROM brigades WHERE is_active = true")
            
            if not brigades:
                return
            
            for (user_id,) in brigades:
                # Проверяем, есть ли уже запись для этого пользователя
                existing = await db_query(
                    "SELECT id FROM scheduled_notifications WHERE user_id = %s AND notification_type = 'roster_reminder'",
                    (user_id,)
                )
                
                if not existing:
                    # Создаем запись для напоминания в 8:00
                    await db_execute("""
                        INSERT INTO scheduled_notifications (user_id, notification_type, scheduled_time, is_active)
                        VALUES (%s, 'roster_reminder', '08:00:00', true)
                    """, (user_id,))
            
            logger.info("Настройка ежедневных напоминаний завершена")
            
        except Exception as e:
            logger.error(f"Ошибка настройки ежедневных напоминаний: {e}")
    
    @staticmethod
    async def process_scheduled_notifications(context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает запланированные уведомления (вызывается по расписанию)"""
        try:
            current_time = datetime.now().time()
            current_date = date.today()
            
            # Находим уведомления, которые нужно отправить
            notifications = await db_query("""
                SELECT user_id, notification_type 
                FROM scheduled_notifications 
                WHERE scheduled_time <= %s 
                AND is_active = true 
                AND (last_sent IS NULL OR last_sent < %s)
            """, (current_time, current_date))
            
            for user_id, notification_type in notifications:
                if notification_type == 'roster_reminder':
                    await NotificationService.send_roster_reminder(context, user_id)
            
        except Exception as e:
            logger.error(f"Ошибка обработки запланированных уведомлений: {e}")
    
    @staticmethod
    async def get_users_for_discipline_notification(discipline_name: str, role: str) -> List[str]:
        """Получает список пользователей определенной роли для дисциплины"""
        try:
            if role == 'master':
                query = """
                    SELECT m.user_id FROM masters m
                    JOIN disciplines d ON m.discipline_id = d.id
                    WHERE d.name = %s AND m.is_active = true AND m.can_approve_reports = true
                """
            elif role == 'kiok':
                query = """
                    SELECT k.user_id FROM kiok k
                    JOIN disciplines d ON k.discipline_id = d.id
                    WHERE d.name = %s AND k.is_active = true
                """
            else:
                return []
            
            results = await db_query(query, (discipline_name,))
            return [row[0] for row in results] if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения пользователей для уведомлений: {e}")
            return []
        
        # --- > НОВАЯ ФУНКЦИЯ ДЛЯ НАПОМИНАНИЙ <---
   
    # --- > ДОБАВЬТЕ ЭТУ ФУНКЦИЮ В КОНЕЦ КЛАССА <---
    @staticmethod
    async def send_pending_report_reminders(bot: ExtBot):
        """
        Находит отчеты, ожидающие подтверждения мастером более 2 дней,
        и отправляет напоминания соответствующим мастерам.
        """
        logger.info("Scheduler: Запуск проверки зависших отчетов для мастеров...")
        try:
            overdue_reports = await db_query("""
                SELECT id, discipline_id, supervisor_id, brigade_name, work_type_name
                FROM reports
                WHERE workflow_status = 'pending_master'
                  AND created_at <= NOW() - INTERVAL '2 days';
            """)

            if not overdue_reports:
                logger.info("Scheduler: Зависших отчетов не найдено.")
                return

            logger.info(f"Scheduler: Найдено {len(overdue_reports)} зависших отчетов.")
            
            for report_id, discipline_id, supervisor_id, brigade_name, work_type in overdue_reports:
                masters = await db_query(
                    "SELECT user_id FROM masters WHERE discipline_id = %s AND is_active = true",
                    (discipline_id,)
                )
                if not masters:
                    continue

                supervisor_name_res = await db_query("SELECT supervisor_name FROM supervisors WHERE user_id = %s", (supervisor_id,))
                supervisor_name = supervisor_name_res[0][0] if supervisor_name_res else f"ID: {supervisor_id}"
                
                for (master_id,) in masters:
                    lang = await get_user_language(master_id)
                    text = get_text('master_report_reminder_notification', lang).format(
                        report_id=report_id,
                        supervisor=escape_markdown(supervisor_name, version=2),
                        brigade=escape_markdown(brigade_name, version=2),
                        work_type=escape_markdown(work_type, version=2)
                    )
                    keyboard = [[InlineKeyboardButton(get_text('view_details_button', lang), callback_data=f"master_view_{report_id}")]]
                    
                    try:
                        await bot.send_message(
                            chat_id=master_id,
                            text=text,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode=ParseMode.MARKDOWN_V2
                        )
                        logger.info(f"Отправлено напоминание по отчету {report_id} мастеру {master_id}")
                    except Exception as e:
                        logger.error(f"Не удалось отправить напоминание мастеру {master_id}: {e}")

        except Exception as e:
            logger.error(f"Ошибка в процессе отправки напоминаний о зависших отчетах: {e}")