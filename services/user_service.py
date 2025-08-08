# services/user_service.py

import logging
from typing import Optional, Dict, Any
from database.queries import db_query, db_execute  # ASYNC версии

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления пользователями"""
    
    @staticmethod
    async def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
        """ASYNC получение информации о пользователе с дисциплиной - ИСПРАВЛЕНО"""
        from config.settings import OWNER_ID
        
        # FIXED: Специальная обработка для OWNER_ID
        if str(user_id) == str(OWNER_ID):
            return {
                'user_id': user_id,
                'phone_number': 'System',
                'language_code': 'ru',
                'first_name': 'System',
                'last_name': 'Owner', 
                'role_table': 'owner',
                'full_name': 'System Owner',
                'discipline_name': 'Все дисциплины'  # ADDED
            }
        
        # Таблицы с first_name, last_name
        standard_tables = ['admins', 'managers', 'brigades', 'pto']
        for table in standard_tables:
            if table == 'admins':
                # Админы не имеют дисциплины
                result = await db_query(
                    f"SELECT user_id, phone_number, language_code, first_name, last_name FROM {table} WHERE user_id = %s", 
                    (user_id,)
                )
                if result:
                    user_data = result[0]
                    return {
                        'user_id': user_data[0], 
                        'phone_number': user_data[1],
                        'language_code': user_data[2] or 'ru',
                        'first_name': user_data[3] or '',
                        'last_name': user_data[4] or '',
                        'role_table': table,
                        'discipline_name': 'Все дисциплины'  # ADDED
                    }
            else:
                # Другие таблицы имеют дисциплины
                discipline_field = 'discipline' if table == 'managers' else 'discipline_id'
                result = await db_query(
                    f"""SELECT u.user_id, u.phone_number, u.language_code, u.first_name, u.last_name, 
                        d.name as discipline_name 
                        FROM {table} u 
                        LEFT JOIN disciplines d ON u.{discipline_field} = d.id 
                        WHERE u.user_id = %s""", 
                    (user_id,)
                )
                if result:
                    user_data = result[0]
                    return {
                        'user_id': user_data[0], 
                        'phone_number': user_data[1],
                        'language_code': user_data[2] or 'ru',
                        'first_name': user_data[3] or '',
                        'last_name': user_data[4] or '',
                        'role_table': table,
                        'discipline_name': user_data[5] or 'Не указана'  # ADDED
                    }
        
        # Таблицы с именными полями
        special_tables = {
            'supervisors': 'supervisor_name',
            'masters': 'master_name', 
            'kiok': 'kiok_name'
        }
        
        for table, name_field in special_tables.items():
            result = await db_query(
                f"""SELECT u.user_id, u.phone_number, u.language_code, u.{name_field}, 
                    d.name as discipline_name 
                    FROM {table} u 
                    LEFT JOIN disciplines d ON u.discipline_id = d.id 
                    WHERE u.user_id = %s""", 
                (user_id,)
            )
            if result:
                user_data = result[0]
                full_name = user_data[3] or ''
                # FIXED: Разбиваем полное имя на части
                name_parts = full_name.split(' ', 1)
                first_name = name_parts[0] if name_parts else ''
                last_name = name_parts[1] if len(name_parts) > 1 else ''
                
                return {
                    'user_id': user_data[0], 
                    'phone_number': user_data[1],
                    'language_code': user_data[2] or 'ru',
                    'first_name': first_name,
                    'last_name': last_name,
                    'role_table': table,
                    'full_name': full_name,
                    'discipline_name': user_data[4] or 'Не указана'  # ADDED
                }
        
        return None

    @staticmethod
    async def update_user_language(user_id: str, language_code: str) -> bool:
        """ASYNC обновление языка пользователя"""
        tables = ['admins', 'managers', 'brigades', 'pto', 'kiok', 'supervisors', 'masters']
        updated = False
        for table in tables:
            if await db_query(f"SELECT 1 FROM {table} WHERE user_id = %s", (user_id,)):
                if await db_execute(f"UPDATE {table} SET language_code = %s WHERE user_id = %s", (language_code, user_id)):
                    updated = True
        return updated