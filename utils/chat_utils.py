"""
Утилиты для работы с чатом (финальная, универсальная версия)
"""

import logging
from telegram import Update, Message
from telegram.ext import ContextTypes
from functools import wraps

logger = logging.getLogger(__name__)

async def clean_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """
    Удаляет все сообщения, помеченные для очистки. 
    Теперь это самостоятельная функция, которую можно вызывать вручную.
    """
    message_ids = context.user_data.pop('tracked_messages', [])
    if not message_ids:
        return

    for message_id in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
    logger.debug(f"Очищено {len(message_ids)} сообщений в чате {chat_id}")

async def track_message(context: ContextTypes.DEFAULT_TYPE, message: Message):
    """
    Добавляет ID сообщения в список для отслеживания.
    Теперь это самостоятельная функция.
    """
    if 'tracked_messages' not in context.user_data:
        context.user_data['tracked_messages'] = []
    if message:
        context.user_data['tracked_messages'].append(message.message_id)

def auto_clean(func):
    """
    Декоратор для простых обработчиков кнопок (CallbackQueryHandler).
    Автоматически чистит чат и отслеживает новое сообщение.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = update.effective_chat.id
        await clean_chat(context, chat_id)
        
        result_message = await func(update, context, *args, **kwargs)
        
        if result_message:
            await track_message(context, result_message)
        
        return result_message
    return wrapper