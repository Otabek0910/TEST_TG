# bot/middleware/state_manager.py

import logging
from typing import Dict, Any, Optional
from enum import Enum
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

class UserState(Enum):
    """Состояния пользователей"""
    # Auth states
    SELECTING_ROLE = "selecting_role"
    GETTING_NAME = "getting_name" 
    GETTING_CONTACT = "getting_contact"
    SELECTING_MANAGER_LEVEL = "selecting_manager_level"
    SELECTING_DISCIPLINE = "selecting_discipline"
    
    # Report states
    SELECTING_BRIGADE = "selecting_brigade"
    GETTING_CORPUS = "getting_corpus"
    GETTING_WORK_TYPE = "getting_work_type"
    GETTING_PIPE_DATA = "getting_pipe_data"
    CONFIRM_REPORT = "confirm_report"
    
    # Roster states
    AWAITING_ROLES_COUNT = "awaiting_roles_count"
    CONFIRM_ROSTER = "confirm_roster"
    CONFIRM_DANGEROUS_ROSTER_SAVE = "confirm_dangerous_roster_save"
    
    # Admin states
    AWAITING_NEW_DISCIPLINE = "awaiting_new_discipline"
    AWAITING_NEW_LEVEL = "awaiting_new_level"
    GETTING_HR_DATE = "getting_hr_date"
    AWAITING_RESTORE_FILE = "awaiting_restore_file"
    
    # Workflow states
    AWAITING_MASTER_REJECTION = "awaiting_master_rejection"
    AWAITING_KIOK_INSPECTION_NUM = "awaiting_kiok_inspection_num"
    AWAITING_KIOK_REJECTION = "awaiting_kiok_rejection"

class StateManager:
    """Надежный менеджер состояний пользователей"""
    
    @staticmethod
    def _ensure_user_states(context) -> Dict:
        """Инициализирует хранилище состояний если его нет"""
        if 'user_states' not in context.bot_data:
            context.bot_data['user_states'] = {}
        return context.bot_data['user_states']
    
    @staticmethod
    def set_state(context, user_id: str, state: UserState, data: Optional[Dict[str, Any]] = None) -> None:
        """Устанавливает состояние пользователя с данными"""
        user_states = StateManager._ensure_user_states(context)
        
        user_states[user_id] = {
            'current_state': state.value,
            'data': data or {},
            'updated_at': context.bot_data.get('current_time', 'unknown')
        }
        
        logger.debug(f"Set state for user {user_id}: {state.value}")
    
    @staticmethod
    def get_state(context, user_id: str) -> Optional[Dict[str, Any]]:
        """Получает текущее состояние пользователя"""
        user_states = StateManager._ensure_user_states(context)
        return user_states.get(user_id)
    
    @staticmethod
    def get_current_state(context, user_id: str) -> Optional[UserState]:
        """Получает только текущее состояние без данных"""
        state_data = StateManager.get_state(context, user_id)
        if state_data:
            try:
                return UserState(state_data['current_state'])
            except ValueError:
                logger.warning(f"Unknown state for user {user_id}: {state_data['current_state']}")
        return None
    
    @staticmethod
    def get_state_data(context, user_id: str) -> Dict[str, Any]:
        """Получает данные состояния пользователя"""
        state_data = StateManager.get_state(context, user_id)
        return state_data.get('data', {}) if state_data else {}
    
    @staticmethod
    def update_state_data(context, user_id: str, new_data: Dict[str, Any]) -> None:
        """Обновляет данные состояния без смены состояния"""
        user_states = StateManager._ensure_user_states(context)
        if user_id in user_states:
            user_states[user_id]['data'].update(new_data)
            logger.debug(f"Updated state data for user {user_id}")
    
    @staticmethod
    def clear_state(context, user_id: str) -> None:
        """Очищает состояние пользователя"""
        user_states = StateManager._ensure_user_states(context)
        if user_id in user_states:
            del user_states[user_id]
            logger.debug(f"Cleared state for user {user_id}")
    
    @staticmethod
    def is_in_state(context, user_id: str, expected_state: UserState) -> bool:
        """Проверяет, находится ли пользователь в определенном состоянии"""
        current_state = StateManager.get_current_state(context, user_id)
        return current_state == expected_state
    
    @staticmethod
    def require_state(context, user_id: str, expected_state: UserState) -> bool:
        """Проверяет состояние с логированием ошибки если не совпадает"""
        if not StateManager.is_in_state(context, user_id, expected_state):
            current = StateManager.get_current_state(context, user_id)
            logger.warning(f"User {user_id} not in expected state {expected_state.value}, current: {current}")
            return False
        return True

class StateDecorator:
    """Декораторы для проверки состояний"""
    
    @staticmethod
    def require_state(expected_state: UserState):
        """Декоратор для проверки состояния перед выполнением функции"""
        def decorator(func):
            async def wrapper(update, context, *args, **kwargs):
                user_id = str(update.effective_user.id)
                
                if not StateManager.require_state(context, user_id, expected_state):
                    reply_markup = InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")
                    ]])
                    
                    await update.effective_message.reply_text(
                        "❌ Неверная последовательность действий. Начните сначала.",
                        reply_markup=reply_markup
                    )
                    return
                
                return await func(update, context, *args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def clear_state_after(func):
        """Декоратор для очистки состояния после выполнения функции"""
        async def wrapper(update, context, *args, **kwargs):
            result = await func(update, context, *args, **kwargs)
            user_id = str(update.effective_user.id)
            StateManager.clear_state(context, user_id)
            return result
        return wrapper