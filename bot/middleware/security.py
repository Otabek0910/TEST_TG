# bot/middleware/security.py

import logging
from functools import wraps
from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import ContextTypes

from config.settings import OWNER_ID
from database.queries import db_query_sync  # FIXED: используем синхронную версию
from utils.localization import get_user_language

logger = logging.getLogger(__name__)

def check_user_role(user_id: str) -> Dict[str, Any]:
    """СИНХРОННАЯ проверка роли пользователя (ИСПРАВЛЕНО)"""
    user_id_str = str(user_id)
    
    if user_id_str == OWNER_ID:
        return {
            'isAdmin': True, 'isManager': True, 'isSupervisor': True, 'isMaster': True,
            'isForeman': True, 'isPto': True, 'isKiok': True, 'managerLevel': 1,
            'discipline': None, 'supervisorName': 'Owner', 'assignedBrigades': [],
            'userId': user_id_str
        }
    
    user_role = {'userId': user_id_str}
    
    try:
        # Админы
        admin_check = db_query_sync("SELECT user_id FROM admins WHERE user_id = %s", (user_id_str,))
        if admin_check:
            user_role['isAdmin'] = True
        
        # Менеджеры - используем 'discipline', не 'discipline_id'
        manager_check = db_query_sync(
            "SELECT level, discipline, d.name FROM managers m LEFT JOIN disciplines d ON m.discipline = d.id WHERE m.user_id = %s", 
            (user_id_str,)
        )
        if manager_check:
            user_role['isManager'] = True
            user_role['managerLevel'] = manager_check[0][0]
            user_role['disciplineId'] = manager_check[0][1]
            user_role['discipline'] = manager_check[0][2]
        
        # Супервайзеры - используем 'discipline_id'
        supervisor_check = db_query_sync(
            """SELECT supervisor_name, discipline_id, brigade_ids, d.name as discipline_name 
               FROM supervisors s LEFT JOIN disciplines d ON s.discipline_id = d.id 
               WHERE s.user_id = %s""", 
            (user_id_str,)
        )
        if supervisor_check:
            user_role['isSupervisor'] = True
            user_role['supervisorName'] = supervisor_check[0][0]
            user_role['disciplineId'] = supervisor_check[0][1]
            user_role['discipline'] = supervisor_check[0][3]
            user_role['assignedBrigades'] = supervisor_check[0][2] or []
        
        # Мастера - используем 'discipline_id'
        master_check = db_query_sync(
            """SELECT master_name, discipline_id, d.name as discipline_name 
               FROM masters m LEFT JOIN disciplines d ON m.discipline_id = d.id 
               WHERE m.user_id = %s""", 
            (user_id_str,)
        )
        if master_check:
            user_role['isMaster'] = True
            user_role['masterName'] = master_check[0][0]
            user_role['disciplineId'] = master_check[0][1]
            user_role['discipline'] = master_check[0][2]
        
        # Бригадиры - используем 'discipline_id'
        foreman_check = db_query_sync(
            "SELECT brigade_name, discipline_id, d.name FROM brigades b LEFT JOIN disciplines d ON b.discipline_id = d.id WHERE b.user_id = %s", 
            (user_id_str,)
        )
        if foreman_check:
            user_role['isForeman'] = True
            user_role['isBrigade'] = True  # Для совместимости
            user_role['brigadeName'] = foreman_check[0][0]
            user_role['disciplineId'] = foreman_check[0][1]
            user_role['discipline'] = foreman_check[0][2]
        
        # ПТО - используем 'discipline_id'
        pto_check = db_query_sync(
            "SELECT d.name FROM pto p LEFT JOIN disciplines d ON p.discipline_id = d.id WHERE p.user_id = %s", 
            (user_id_str,)
        )
        if pto_check:
            user_role['isPto'] = True
            user_role['discipline'] = pto_check[0][0]
        
        # КИОК - используем 'discipline_id'
        kiok_check = db_query_sync(
            "SELECT d.name FROM kiok k LEFT JOIN disciplines d ON k.discipline_id = d.id WHERE k.user_id = %s", 
            (user_id_str,)
        )
        if kiok_check:
            user_role['isKiok'] = True
            user_role['discipline'] = kiok_check[0][0]
            
    except Exception as e:
        logger.error(f"Ошибка проверки роли для пользователя {user_id_str}: {e}")
    
    return user_role

async def security_gateway(func):
    """Декоратор для проверки прав доступа"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        user_id = str(user.id)
        user_role = check_user_role(user_id)  # СИНХРОННЫЙ вызов
        
        context.user_data['user_role'] = user_role
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper