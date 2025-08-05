# services/admin_service.py

import logging
from typing import Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.settings import OWNER_ID
from database.queries import db_query, db_execute

logger = logging.getLogger(__name__)

class AdminService:
    """Сервис для админских операций (ИСПРАВЛЕННАЯ ВЕРСИЯ)"""
    
    @staticmethod
    async def get_admin_list():
        """ASYNC получение списка админов"""
        admin_ids_raw = await db_query("SELECT user_id FROM admins")
        admin_ids = [row[0] for row in admin_ids_raw] if admin_ids_raw else []
        return list(set(admin_ids + [OWNER_ID]))
    
    @staticmethod
    async def send_approval_request(
        context: ContextTypes.DEFAULT_TYPE,
        user_data: Dict[str, Any],
        user_id: str
    ) -> bool:
        """Отправка запроса на одобрение админам - ИСПРАВЛЕНО для StateManager"""
        try:
            # FIXED: Детальное логирование для отладки
            logger.info(f"DEBUG >>> ПОЛУЧИЛИ user_data: {user_data}")
            logger.info(f"DEBUG >>> Ключи в user_data: {list(user_data.keys())}")
            
            # FIXED: Проверяем обязательные поля
            required_fields = ['selected_role', 'first_name', 'last_name', 'phone_number']
            missing_fields = [field for field in required_fields if not user_data.get(field)]
            
            if missing_fields:
                logger.error(f"DEBUG >>> ОТСУТСТВУЮТ ОБЯЗАТЕЛЬНЫЕ ПОЛЯ: {missing_fields}")
                logger.error(f"DEBUG >>> ПОЛНЫЕ ДАННЫЕ: {user_data}")
                return False
            
            # FIXED: Сохраняем данные в правильном месте для обработчика одобрения
            context.bot_data[user_id] = user_data
            logger.info(f"DEBUG >>> СОХРАНИЛИ в context.bot_data[{user_id}]: {context.bot_data.get(user_id)}")
            
            # FIXED: Добавлены новые роли для корректного отображения
            role_map = {
                'foreman': 'Бригадир', 'manager': 'Менеджер', 'pto': 'ПТО',
                'kiok': 'КИОК', 'supervisor': 'Супервайзер', 'master': 'Мастер'
            }
            role_key = user_data.get('selected_role', 'unknown')
            role_text = role_map.get(role_key, role_key.capitalize())
            
            discipline_text = ""
            if user_data.get('discipline_id'):
                disc_result = await db_query("SELECT name FROM disciplines WHERE id = %s", (user_data['discipline_id'],))
                if disc_result:
                    discipline_text = f"\n📋 Дисциплина: {disc_result[0][0]}"
            
            level_text = ""
            if user_data.get('manager_level'):
                level_text = f"\n⚙️ Уровень: {user_data['manager_level']}"
            
            # FIXED: Проверяем наличие телефона и выводим его корректно
            phone_number = user_data.get('phone_number', 'Не указан')
            logger.info(f"DEBUG >>> Номер телефона для отправки: {phone_number}")
            
            request_text = (
                f"🔐 <b>Запрос на авторизацию</b>\n\n"
                f"👤 Имя: {user_data.get('first_name', '')} {user_data.get('last_name', '')}\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"👔 Роль: {role_text}"
                f"{discipline_text}{level_text}\n"
                f"📞 Телефон: {phone_number}\n\n"
                f"Одобрить заявку?"
            )
            
            approve_callback = f"approve_{role_key}_{user_id}"
            reject_callback = f"reject_{role_key}_{user_id}"
            
            keyboard = [[
                InlineKeyboardButton("✅ Одобрить", callback_data=approve_callback),
                InlineKeyboardButton("❌ Отклонить", callback_data=reject_callback)
            ]]
            
            admins = await AdminService.get_admin_list()
            for admin_id in admins:
                try:
                    await context.bot.send_message(
                        admin_id, request_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.HTML
                    )
                    logger.info(f"DEBUG >>> Запрос отправлен админу {admin_id}")
                except Exception as e:
                    logger.error(f"Не удалось отправить запрос админу {admin_id}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки запроса на одобрение: {e}")
            return False
    
    @staticmethod
    async def create_user_in_db(user_data: Dict[str, Any], user_id: str) -> bool:
        """Создание пользователя в соответствующей таблице БД - ИСПРАВЛЕНО под реальную схему"""
        try:
            role = user_data.get('selected_role')
            first_name = user_data.get('first_name', '')
            last_name = user_data.get('last_name', '')
            phone = user_data.get('phone_number', '')
            discipline_id = user_data.get('discipline_id')
            
            # FIXED: Исправлены запросы под реальную схему БД
            if role == 'supervisor':
                supervisor_name = f"{first_name} {last_name}"
                result = await db_execute(
                    """INSERT INTO supervisors (user_id, supervisor_name, discipline_id, phone_number) 
                       VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET
                       supervisor_name = EXCLUDED.supervisor_name,
                       discipline_id = EXCLUDED.discipline_id,
                       phone_number = EXCLUDED.phone_number""",
                    (user_id, supervisor_name, discipline_id, phone)
                )
                
            elif role == 'master':
                master_name = f"{first_name} {last_name}"
                result = await db_execute(
                    """INSERT INTO masters (user_id, master_name, discipline_id, phone_number) 
                       VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET
                       master_name = EXCLUDED.master_name,
                       discipline_id = EXCLUDED.discipline_id,
                       phone_number = EXCLUDED.phone_number""",
                    (user_id, master_name, discipline_id, phone)
                )
                
            elif role == 'foreman':
                brigade_name = f"{first_name} {last_name}"
                result = await db_execute(
                    """INSERT INTO brigades (user_id, brigade_name, discipline_id, first_name, last_name, phone_number) 
                       VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET
                       brigade_name = EXCLUDED.brigade_name,
                       discipline_id = EXCLUDED.discipline_id,
                       first_name = EXCLUDED.first_name,
                       last_name = EXCLUDED.last_name,
                       phone_number = EXCLUDED.phone_number""",
                    (user_id, brigade_name, discipline_id, first_name, last_name, phone)
                )
                
            elif role == 'manager':
                level = user_data.get('manager_level', 2)
                # Для Уровня 1 discipline_id может быть NULL
                final_discipline_id = discipline_id if level == 2 else None
                result = await db_execute(
                    """INSERT INTO managers (user_id, level, discipline, first_name, last_name, phone_number) 
                       VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET
                       level = EXCLUDED.level,
                       discipline = EXCLUDED.discipline,
                       first_name = EXCLUDED.first_name,
                       last_name = EXCLUDED.last_name,
                       phone_number = EXCLUDED.phone_number""",
                    (user_id, level, final_discipline_id, first_name, last_name, phone)
                )
                
            elif role == 'pto':
                result = await db_execute(
                    """INSERT INTO pto (user_id, discipline_id, first_name, last_name, phone_number) 
                       VALUES (%s, %s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET
                       discipline_id = EXCLUDED.discipline_id,
                       first_name = EXCLUDED.first_name,
                       last_name = EXCLUDED.last_name,
                       phone_number = EXCLUDED.phone_number""",
                    (user_id, discipline_id, first_name, last_name, phone)
                )
                
            elif role == 'kiok':
                kiok_name = f"{first_name} {last_name}"
                result = await db_execute(
                    """INSERT INTO kiok (user_id, kiok_name, discipline_id, phone_number) 
                       VALUES (%s, %s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET
                       kiok_name = EXCLUDED.kiok_name,
                       discipline_id = EXCLUDED.discipline_id,
                       phone_number = EXCLUDED.phone_number""",
                    (user_id, kiok_name, discipline_id, phone)
                )
                
            else:
                logger.error(f"Неизвестная роль: {role}")
                return False
            
            logger.info(f"Пользователь {user_id} создан с ролью {role}, затронуто строк: {result}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Ошибка создания пользователя в БД: {e}")
            return False