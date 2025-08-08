# utils/constants.py - ИСПРАВЛЕНИЯ

import os

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'temp_files')
"""
Константы, используемые в разных частях бота, в основном для состояний ConversationHandler.
"""

# --- Состояния для ConversationHandler'ов ---
# Используем range для генерации уникальных целых чисел для состояний.

(
    # Auth Flow (bot/conversations/auth_flow.py)
    SELECTING_ROLE, 
    GETTING_NAME, 
    GETTING_CONTACT, 
    SELECTING_MANAGER_LEVEL, 
    SELECTING_DISCIPLINE,

    # Report Flow (bot/conversations/report_flow.py)
    SELECTING_BRIGADE, 
    GETTING_CORPUS_NEW, 
    GETTING_WORK_TYPE_NEW,
    GETTING_PIPE_DATA, 
    CONFIRM_REPORT_NEW,

    # Roster Flow
    AWAITING_ROLES_COUNT, 
    CONFIRM_ROSTER, 
    CONFIRM_DANGEROUS_ROSTER_SAVE,
    INTERACTIVE_ROSTER_EDIT,      # ADDED: интерактивный режим

    # Analytics Flow (bot/handlers/analytics.py)
    SELECTING_OVERVIEW_ACTION, 
    AWAITING_OVERVIEW_DATE,
    
    # Workflow/Rejection Flow (bot/handlers/workflow.py)
    AWAITING_MASTER_REJECTION, 
    AWAITING_KIOK_INSPECTION_NUM, 
    AWAITING_KIOK_REJECTION,
    
    # Admin Management Flow
    AWAITING_NEW_DISCIPLINE,
    AWAITING_NEW_LEVEL,
    AWAITING_NEW_VALUE,
    
    # HR Date Selection Flow  
    GETTING_HR_DATE,
    
    # DB Restore Flow
    AWAITING_RESTORE_FILE,
    
    # Language Selection
    SELECTING_LANGUAGE
) = range(25)

# --- Другие константы ---
TEMP_DIR = 'temp_files'

# --- Константы пагинации ---
USERS_PER_PAGE = 10
REPORTS_PER_PAGE = 5

# --- Роли пользователей ---
USER_ROLES = {
    'admins': 'Администраторы',
    'managers': 'Менеджеры', 
    'supervisors': 'Супервайзеры',
    'masters': 'Мастера',
    'brigades': 'Бригадиры',
    'pto': 'ПТО',
    'kiok': 'КИОК'
}

# --- Статусы отчетов ---
REPORT_STATUS_LABELS = {
    'draft': 'Черновик',
    'pending_master': 'Ожидает мастера',
    'pending_kiok': 'Ожидает КИОК',
    'approved': 'Одобрен',
    'rejected': 'Отклонен'
}

# FIXED: Убираем дублирование ALL_TABLE_NAMES_FOR_BACKUP
ALL_TABLE_NAMES_FOR_BACKUP = [
    'disciplines',
    'construction_objects', 
    'work_types',
    'personnel_roles',
    'admins',
    'managers',
    'supervisors',
    'masters',
    'brigades',
    'pto',
    'kiok',
    'reports',
    'brigades_reference',
    'daily_rosters',
    'daily_roster_details',
    'topic_mappings',
    'scheduled_notifications'
]

MAX_PHOTO_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/jpg']

WORKFLOW_STATUSES = {
    'draft': 'Черновик',
    'pending_master': 'Ожидает мастера',
    'pending_kiok': 'Ожидает КИОК',
    'approved': 'Утвержден',
    'rejected': 'Отклонен'
}