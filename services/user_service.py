# services/user_service.py

import logging
from typing import Optional, Dict, Any
from database.queries import db_query, db_execute  # ASYNC версии

logger = logging.getLogger(__name__)

class UserService:
    """Сервис для управления пользователями"""
    
    @staticmethod
    async def get_user_info(user_id: str) -> Optional[Dict[str, Any]]:
        """ASYNC получение информации о пользователе"""
        tables = ['admins', 'managers', 'brigades', 'pto', 'kiok', 'supervisors', 'masters']
        for table in tables:
            result = await db_query(f"SELECT user_id, phone_number, language_code FROM {table} WHERE user_id = %s", (user_id,))
            if result:
                user_data = result[0]
                return {
                    'user_id': user_data[0], 
                    'phone_number': user_data[1],
                    'language_code': user_data[2] or 'ru', 
                    'role_table': table
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