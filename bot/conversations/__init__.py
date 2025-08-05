# bot/conversations/__init__.py

"""
ConversationHandler'ы для сложных диалогов - ОБНОВЛЕННАЯ ВЕРСИЯ
"""

# REMOVED: auth_flow - теперь используем auth_new.py без ConversationHandler
from .report_flow import create_report_conversation

__all__ = ['create_report_conversation']