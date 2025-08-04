# services/user_management_service.py

import logging
from typing import Dict, Any, List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from database.queries import db_query, db_execute
from utils.localization import get_user_language, get_text
from config.settings import OWNER_ID

logger = logging.getLogger(__name__)

class UserManagementService:
    """Сервис для управления пользователями"""

    USERS_PER_PAGE = 5
    
    @staticmethod
    async def show_user_edit_menu(query, role: str, user_id_to_edit: str, viewer_id: str) -> None:
        """Показывает меню редактирования конкретного пользователя"""
        try:
            # Получаем данные пользователя
            user_data = await db_query(f"SELECT first_name, last_name, username, phone_number FROM {role} WHERE user_id = %s", (user_id_to_edit,))
            
            if not user_data:
                await query.edit_message_text("❌ Пользователь не найден.")
                return
                
            first_name = user_data[0][0] or ""
            last_name = user_data[0][1] or ""
            username = user_data[0][2] or ""
            phone = user_data[0][3] or ""
            
            # Получаем дополнительные данные в зависимости от роли
            role_info = await UserManagementService.get_role_specific_info(role, user_id_to_edit)
            
            # Формируем текст с информацией о пользователе
            user_info_lines = [
                f"👤 **Пользователь: {first_name} {last_name}**",
                f"🆔 ID: `{user_id_to_edit}`",
                f"👤 Username: @{username}" if username else "👤 Username: Отсутствует",
                f"📱 Телефон: {phone}" if phone else "📱 Телефон: Не указан",
                f"📋 **Роль: {UserManagementService.get_role_display_name(role)}**",
            ]
            
            # Добавляем специфичную для роли информацию
            if role_info:
                user_info_lines.extend(role_info)
                
            # Формируем кнопки для управления пользователем
            keyboard = []
            
            # Кнопка изменения роли (доступна только для админов)
            is_admin = await UserManagementService.is_admin(viewer_id)
            if is_admin:
                keyboard.append([InlineKeyboardButton("🔄 Изменить роль", callback_data=f"change_role_{role}_{user_id_to_edit}")])
            
            # Кнопки управления в зависимости от роли
            if role == "managers":
                keyboard.append([InlineKeyboardButton("🏢 Изменить дисциплину", callback_data=f"change_discipline_{user_id_to_edit}")])
                keyboard.append([InlineKeyboardButton("🔝 Изменить уровень", callback_data=f"change_level_{user_id_to_edit}")])
            
            if role in ["brigades", "masters", "supervisors"]:
                keyboard.append([InlineKeyboardButton("🧾 Сбросить табель", callback_data=f"reset_roster_{role}_{user_id_to_edit}")])
            
            if is_admin:
                keyboard.append([InlineKeyboardButton("❌ Удалить пользователя", callback_data=f"delete_user_{role}_{user_id_to_edit}")])
            
            # Кнопка возврата
            keyboard.append([InlineKeyboardButton("◀️ Назад к списку", callback_data=f"list_users_{role}_1")])
            
            await query.edit_message_text(
                text="\n".join(user_info_lines),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Ошибка при отображении меню редактирования пользователя: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка при загрузке данных пользователя.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="manage_users")
                ]])
            )
    
    @staticmethod
    async def get_role_specific_info(role: str, user_id: str) -> List[str]:
        """Получает специфичную для роли информацию о пользователе"""
        info_lines = []
        
        try:
            if role == "managers":
                manager_data = db_query("SELECT manager_level, discipline FROM managers WHERE user_id = %s", (user_id,))
                if manager_data:
                    level = manager_data[0][0]
                    discipline_id = manager_data[0][1]
                    
                    # Получаем название дисциплины, если есть
                    discipline_name = "Не указана"
                    if discipline_id:
                        discipline_data = db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,))
                        if discipline_data:
                            discipline_name = discipline_data[0][0]
                    
                    level_text = "Полный доступ" if level == 1 else f"Уровень {level}"
                    info_lines.append(f"🔰 Уровень: **{level_text}**")
                    info_lines.append(f"🏢 Дисциплина: **{discipline_name}**")
            
            elif role in ["brigades", "masters", "supervisors"]:
                # Для бригадиров, мастеров и супервайзеров получаем информацию о бригаде и дисциплине
                query_text = f"SELECT brigade_name, discipline FROM {role} WHERE user_id = %s"
                role_data = db_query(query_text, (user_id,))
                
                if role_data:
                    brigade_name = role_data[0][0] or "Не указана"
                    discipline_id = role_data[0][1]
                    
                    # Получаем название дисциплины, если есть
                    discipline_name = "Не указана"
                    if discipline_id:
                        discipline_data = db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,))
                        if discipline_data:
                            discipline_name = discipline_data[0][0]
                    
                    entity_name = "Бригада" if role == "brigades" else "Участок" if role == "masters" else "Направление"
                    info_lines.append(f"🚩 {entity_name}: **{brigade_name}**")
                    info_lines.append(f"🏢 Дисциплина: **{discipline_name}**")
            
            elif role in ["pto", "kiok"]:
                # Для ПТО и КИОК получаем информацию о дисциплине
                role_data = db_query(f"SELECT discipline FROM {role} WHERE user_id = %s", (user_id,))
                
                if role_data:
                    discipline_id = role_data[0][0]
                    
                    # Получаем название дисциплины, если есть
                    discipline_name = "Не указана"
                    if discipline_id:
                        discipline_data = db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,))
                        if discipline_data:
                            discipline_name = discipline_data[0][0]
                    
                    info_lines.append(f"🏢 Дисциплина: **{discipline_name}**")
        
        except Exception as e:
            logger.error(f"Ошибка при получении специфичной информации для роли {role}: {e}")
            info_lines.append("❌ _Ошибка при загрузке дополнительной информации_")
        
        return info_lines
    
    @staticmethod
    def get_role_display_name(role: str) -> str:
        """Возвращает отображаемое название роли"""
        role_names = {
            "admins": "Администратор",
            "managers": "Менеджер",
            "supervisors": "Супервайзер",
            "masters": "Мастер",
            "brigades": "Бригадир",
            "pto": "ПТО",
            "kiok": "КИОК"
        }
        
        return role_names.get(role, "Неизвестная роль")
    
    @staticmethod
    async def is_admin(user_id: str) -> bool:
        """Проверяет, является ли пользователь администратором"""
        if user_id == OWNER_ID:
            return True
            
        admin_data = db_query("SELECT 1 FROM admins WHERE user_id = %s", (user_id,))
        return bool(admin_data)
    
    @staticmethod
    async def list_users_with_pagination(query, role: str, page: int) -> None:
        """Отображает список пользователей с пагинацией"""
        try:
            # Определяем смещение для пагинации
            offset = (page - 1) * UserManagementService.USERS_PER_PAGE
            
            # Получаем общее количество пользователей в роли
            total_users = db_query(f"SELECT COUNT(*) FROM {role}")[0][0]
            
            # Получаем данные пользователей для текущей страницы
            users = db_query(
                f"SELECT user_id, first_name, last_name FROM {role} ORDER BY last_name, first_name LIMIT %s OFFSET %s",
                (UserManagementService.USERS_PER_PAGE, offset)
            )
            
            if not users:
                # Если пользователи не найдены или страница пуста
                if page > 1:
                    # Возвращаемся на первую страницу
                    await UserManagementService.list_users_with_pagination(query, role, 1)
                    return
                else:
                    await query.edit_message_text(
                        f"В категории {UserManagementService.get_role_display_name(role)} пока нет пользователей.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("◀️ Назад", callback_data="manage_users")
                        ]])
                    )
                    return
            
            # Формируем текст со списком пользователей
            user_lines = [f"📋 **Список {UserManagementService.get_role_display_name(role)}ов:**\n"]
            
            for i, user in enumerate(users, 1):
                user_id, first_name, last_name = user
                full_name = f"{first_name or ''} {last_name or ''}".strip() or "Без имени"
                user_lines.append(f"{offset + i}. {full_name}")
            
            # Добавляем информацию о пагинации
            max_page = (total_users + UserManagementService.USERS_PER_PAGE - 1) // UserManagementService.USERS_PER_PAGE
            user_lines.append(f"\nСтраница {page} из {max_page}")
            
            # Формируем клавиатуру
            keyboard = []
            
            # Кнопки редактирования для каждого пользователя
            for user in users:
                user_id, first_name, last_name = user
                full_name = f"{first_name or ''} {last_name or ''}".strip() or "Без имени"
                keyboard.append([
                    InlineKeyboardButton(f"✏️ {full_name}", callback_data=f"edit_user_{role}_{user_id}")
                ])
            
            # Кнопки навигации
            nav_buttons = []
            
            if page > 1:
                nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"list_users_{role}_{page-1}"))
            
            if page < max_page:
                nav_buttons.append(InlineKeyboardButton("➡️ Вперед", callback_data=f"list_users_{role}_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            # Кнопка возврата в меню управления пользователями
            keyboard.append([InlineKeyboardButton("◀️ Вернуться", callback_data="manage_users")])
            
            await query.edit_message_text(
                text="\n".join(user_lines),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        
        except Exception as e:
            logger.error(f"Ошибка при отображении списка пользователей {role}: {e}")
            await query.edit_message_text(
                "❌ Произошла ошибка при загрузке списка пользователей.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Назад", callback_data="manage_users")
                ]])
            )
    
    @staticmethod
    async def delete_user(role: str, user_id: str) -> bool:
        """Удаляет пользователя из указанной роли"""
        try:
            result = db_execute(f"DELETE FROM {role} WHERE user_id = %s", (user_id,))
            logger.info(f"Пользователь {user_id} удален из роли {role}.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при удалении пользователя {user_id} из роли {role}: {e}")
            return False
    
    @staticmethod
    async def reset_roster(user_id: str) -> bool:
        """Сбрасывает сегодняшний табель для пользователя"""
        from datetime import date
        
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            db_execute("DELETE FROM daily_rosters WHERE brigade_user_id = %s AND roster_date = %s", 
                      (user_id, today_str))
            logger.info(f"Табель на {today_str} для пользователя {user_id} сброшен.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сбросе табеля для пользователя {user_id}: {e}")
            return False
    
    @staticmethod
    async def change_discipline(role: str, user_id: str, discipline_id: int) -> bool:
        """Изменяет дисциплину пользователя"""
        try:
            db_execute(f"UPDATE {role} SET discipline = %s WHERE user_id = %s", 
                      (discipline_id, user_id))
            logger.info(f"Для пользователя {user_id} в роли {role} изменена дисциплина на {discipline_id}.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при изменении дисциплины для пользователя {user_id} в роли {role}: {e}")
            return False
    
    @staticmethod
    async def change_manager_level(user_id: str, level: int, discipline_id: Optional[int] = None) -> bool:
        """Изменяет уровень менеджера и, если указана, дисциплину"""
        try:
            if level == 1:
                # Для уровня 1 дисциплина не нужна
                db_execute("UPDATE managers SET level = %s, discipline = NULL WHERE user_id = %s", 
                          (level, user_id))
            else:
                # Для уровня 2 и выше должна быть указана дисциплина
                if discipline_id is None:
                    return False
                
                db_execute("UPDATE managers SET level = %s, discipline = %s WHERE user_id = %s", 
                          (level, discipline_id, user_id))
            
            logger.info(f"Для менеджера {user_id} изменен уровень на {level}.")
            return True
        except Exception as e:
            logger.error(f"Ошибка при изменении уровня менеджера {user_id}: {e}")
            return False