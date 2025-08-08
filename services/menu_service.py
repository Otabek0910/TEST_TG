# services/menu_service.py

"""
Сервис для формирования меню по ролям пользователей - ПОЛНАЯ ВЕРСИЯ
"""

import logging
from typing import List, Dict, Any
from telegram import InlineKeyboardButton

from bot.middleware.security import check_user_role
from config.settings import OWNER_ID, REPORTS_GROUP_URL
from utils.localization import get_text, get_user_language
from database.queries import db_query

try:
    from services.workflow_service import WorkflowService
    WORKFLOW_AVAILABLE = True
except ImportError:
    WORKFLOW_AVAILABLE = False

logger = logging.getLogger(__name__)

class MenuService:
    """Сервис для создания меню в зависимости от роли пользователя"""
    
    @staticmethod
    async def get_main_menu_text_and_buttons(user_id: str):
        """Получает текст и кнопки главного меню для пользователя"""
        user_role = check_user_role(user_id)
        lang =  await get_user_language(user_id)
        
        welcome_text = get_text('welcome_message', lang)
        keyboard_buttons = await MenuService._build_menu_buttons(user_id, user_role, lang)

        return welcome_text, keyboard_buttons
    
    @staticmethod
    def _get_user_role_info(user_role: Dict[str, Any], lang: str) -> str:
        """Получает информацию о роли пользователя для отображения - ИСПРАВЛЕНО"""
        role_parts = []
        
        # FIXED: Проверяем, что user_role не пустой
        if not user_role:
            return "Роль не определена"
        
        # Супервайзер
        if user_role.get('isSupervisor'):
            supervisor_name = user_role.get('supervisorName', 'Неизвестно')
            brigades = user_role.get('assignedBrigades', [])
            brigade_text = f" ({len(brigades)} бригад)" if brigades else ""
            role_parts.append(f"👨‍🔧 {supervisor_name}{brigade_text}")
        
        # Мастер
        if user_role.get('isMaster'):
            master_name = user_role.get('masterName', 'Неизвестно')
            discipline = user_role.get('discipline', 'Неизвестная')
            role_parts.append(f"🔨 {master_name} ({discipline})")
        
        # Бригадир
        if user_role.get('isBrigade'):
            brigade_name = user_role.get('brigadeName', 'Неизвестно')
            role_parts.append(f"👷 Бригадир бригады «{brigade_name}»")
            
        # Менеджер
        if user_role.get('isManager'):
            level = user_role.get('managerLevel', 'Неизвестный')
            if level == 1:
                role_parts.append("👨‍💼 Менеджер (полный доступ)")
            else:
                discipline = user_role.get('discipline', 'Неизвестная')
                role_parts.append(f"👨‍💼 Менеджер дисциплины «{discipline}»")
                
        # ПТО
        if user_role.get('isPto'):
            discipline = user_role.get('discipline', 'Неизвестная')
            role_parts.append(f"🏭 ПТО дисциплины «{discipline}»")
            
        # КИОК
        if user_role.get('isKiok'):
            discipline = user_role.get('discipline', 'Неизвестная')
            role_parts.append(f"📊 КИОК дисциплины «{discipline}»")
            
        # Админ
        if user_role.get('isAdmin'):
            role_parts.append("⚙️ Администратор")
        
        # FIXED: Если ролей нет - возвращаем базовое описание
        if not role_parts:
            return "Пользователь (роль не назначена)"
        
        return " | ".join(role_parts)
    
    @staticmethod
    async def _build_menu_buttons(user_id: str, user_role: Dict[str, Any], lang: str) -> List[List[InlineKeyboardButton]]:
        """Строит кнопки меню в зависимости от роли пользователя"""
        buttons = []
        
        # Список ключей, которые отвечают за реальные роли доступа
        role_keys = ['isSupervisor', 'isMaster', 'isForeman', 'isBrigade', 'isManager', 'isPto', 'isKiok', 'isAdmin']
        
        # Проверяем, есть ли у пользователя хотя бы одна из этих ролей
        is_authorized = any(user_role.get(key) for key in role_keys)

        # --- Меню для АВТОРИЗОВАННЫХ (включая Owner) ---
        if is_authorized or user_id == OWNER_ID:
            # Кнопки по ролям
            if user_id == OWNER_ID:
                buttons.extend([
                    [InlineKeyboardButton("📝 Создать отчет", callback_data="new_report")],
                    [InlineKeyboardButton("📊 Просмотр отчетов", callback_data="report_menu_all")],
                    [InlineKeyboardButton("📈 Аналитика", callback_data="report_historical")],  # ADDED
                    [InlineKeyboardButton("📋 Экспорт данных", callback_data="get_excel_report")],  # ADDED
                    [InlineKeyboardButton("⚙️ Управление", callback_data="manage_menu")]
                ])
            elif user_role.get('isSupervisor'):
                buttons.extend([
                    [InlineKeyboardButton("📝 Создать отчет", callback_data="new_report")],
                    [InlineKeyboardButton("📋 Мои отчеты", callback_data="my_reports")]
                ])
            elif user_role.get('isMaster'):
                # Получаем количество ожидающих отчетов
                pending_count = 0
                if WORKFLOW_AVAILABLE:
                    try:
                        pending_reports = await WorkflowService.get_pending_reports_for_master(user_id)  # FIXED: добавлен await
                        pending_count = len(pending_reports)
                    except Exception as e:
                        logger.error(f"Ошибка получения счетчика для мастера: {e}")
                
                master_button_text = f"✅ Подтвердить отчеты ({pending_count})" if pending_count > 0 else "✅ Подтвердить отчеты"
                buttons.extend([
                    [InlineKeyboardButton(master_button_text, callback_data="approve_reports")],
                    [InlineKeyboardButton("📊 Просмотр отчетов", callback_data="report_menu_all")]
                ])
            elif user_role.get('isForeman') or user_role.get('isBrigade'):
                # Динамически получаем текст для кнопки табеля
                roster_button_text = await MenuService._get_roster_button_text(user_id, lang)
                buttons.extend([
                    [InlineKeyboardButton(roster_button_text, callback_data="submit_roster")]
                ])
            elif user_role.get('isKiok'):
                # Получаем количество ожидающих отчетов для КИОК
                pending_count = 0
                if WORKFLOW_AVAILABLE:
                    try:
                        pending_reports = await WorkflowService.get_pending_reports_for_kiok(user_id)  # FIXED: добавлен await
                        pending_count = len(pending_reports)
                    except Exception as e:
                        logger.error(f"Ошибка получения счетчика для КИОК: {e}")
                
                kiok_button_text = f"🔍 КИОК проверка ({pending_count})" if pending_count > 0 else "🔍 КИОК проверка"
                buttons.extend([
                    [InlineKeyboardButton(kiok_button_text, callback_data="kiok_review")],
                    [InlineKeyboardButton("📊 Просмотр отчетов", callback_data="report_menu_all")],
                    [InlineKeyboardButton("📋 Экспорт данных", callback_data="get_excel_report")]  # ADDED
                ])
            elif user_role.get('isManager') or user_role.get('isPto'):
                buttons.extend([
                    [InlineKeyboardButton("📊 Просмотр отчетов", callback_data="report_menu_all")],
                    [InlineKeyboardButton("📈 Обзорная аналитика", callback_data="report_overview")],  # ADDED
                    [InlineKeyboardButton("📋 Исторические отчеты", callback_data="report_historical")],  # ADDED
                    [InlineKeyboardButton("📋 Экспорт данных", callback_data="get_excel_report")]  # ADDED
                ])
            elif user_role.get('isAdmin'):
                buttons.extend([
                    [InlineKeyboardButton("📊 Просмотр отчетов", callback_data="report_menu_all")],
                    [InlineKeyboardButton("📈 Полная аналитика", callback_data="report_historical")],  # ADDED
                    [InlineKeyboardButton("📋 Экспорт данных", callback_data="get_excel_report")],  # ADDED
                    [InlineKeyboardButton("⚙️ Управление", callback_data="manage_menu")]
                ])
            
            # Общие кнопки для всех авторизованных
            buttons.append([InlineKeyboardButton("👤 Профиль", callback_data="show_profile")])
            if REPORTS_GROUP_URL:
                buttons.append([InlineKeyboardButton("➡️ Группа отчетов", url=REPORTS_GROUP_URL)])

        # --- Меню для НЕАВТОРИЗОВАННЫХ ---
        else:
            buttons.extend([
                [InlineKeyboardButton("🔐 Авторизация", callback_data="start_auth")],
                [InlineKeyboardButton("ℹ️ Информация", callback_data="show_info")]
            ])

        return buttons
    
    @staticmethod
    async def _get_roster_button_text(user_id: str, lang: str) -> str:
        """Получает текст кнопки табеля в зависимости от статуса"""
        from datetime import date
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            if  await db_query("SELECT id FROM daily_rosters WHERE brigade_user_id = %s AND roster_date = %s", (user_id, today_str)):
                return "✅ Табель подан"
            return "📋 Подать табель"
        except Exception:
            return "📋 Подать табель"