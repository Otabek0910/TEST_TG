# database/queries.py

import logging
import asyncio
from functools import partial
from typing import List, Any, Optional, Tuple, Dict, Union

from .connection import db_manager

logger = logging.getLogger(__name__)

# --- СИНХРОННЫЕ ВЕРСИИ ФУНКЦИЙ (для выполнения в отдельном потоке) ---

def _execute_sync(query: str, params: tuple) -> int:
    """[БЛОКИРУЮЩАЯ] Выполняет запрос и возвращает количество затронутых строк."""
    conn = None
    try:
        conn = db_manager.get_sync_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rowcount = cursor.rowcount
        conn.commit()
        return rowcount
    except Exception as e:
        logger.error(f"Ошибка выполнения DB execute: {e}\nЗапрос: {query}")
        if conn:
            conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

def _query_sync(query: str, params: tuple, as_dict: bool = False) -> Optional[List[Union[Tuple, Dict]]]:
    """[БЛОКИРУЮЩАЯ] Выполняет SELECT и возвращает все строки."""
    conn = None
    try:
        conn = db_manager.get_sync_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if as_dict:
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        else:
            return cursor.fetchall()

    except Exception as e:
        logger.error(f"Ошибка выполнения DB query: {e}\nЗапрос: {query}")
        return None
    finally:
        if conn:
            conn.close()

def _query_single_sync(query: str, params: tuple) -> Any:
    """[БЛОКИРУЮЩАЯ] Выполняет SELECT, возвращает одно значение или None."""
    conn = None
    try:
        conn = db_manager.get_sync_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Ошибка выполнения DB query single: {e}\nЗапрос: {query}")
        return None
    finally:
        if conn:
            conn.close()

# --- АСИНХРОННЫЕ ОБЕРТКИ (для использования в боте) ---

async def db_execute(query: str, params: tuple = ()) -> int:
    """Асинхронно выполняет запрос (INSERT, UPDATE, DELETE) и возвращает количество затронутых строк."""
    loop = asyncio.get_running_loop()
    func = partial(_execute_sync, query, params)
    return await loop.run_in_executor(None, func)

async def db_query(query: str, params: tuple = (), as_dict: bool = False) -> Optional[List[Union[Tuple, Dict]]]:
    """Асинхронно выполняет SELECT и возвращает все строки."""
    loop = asyncio.get_running_loop()
    func = partial(_query_sync, query, params, as_dict)
    return await loop.run_in_executor(None, func)

async def db_query_single(query: str, params: tuple = ()) -> Any:
    """Асинхронно выполняет SELECT и возвращает одно значение."""
    loop = asyncio.get_running_loop()
    func = partial(_query_single_sync, query, params)
    return await loop.run_in_executor(None, func)

# --- СИНХРОННЫЕ ОБЕРТКИ (для частых простых запросов) ---

def db_query_sync(query: str, params: tuple = (), as_dict: bool = False) -> Optional[List[Union[Tuple, Dict]]]:
    """Синхронно выполняет SELECT (для check_user_role и подобных)."""
    return _query_sync(query, params, as_dict)

def db_execute_sync(query: str, params: tuple = ()) -> int:
    """Синхронно выполняет запрос (для простых операций)."""
    return _execute_sync(query, params)

def db_query_single_sync(query: str, params: tuple = ()) -> Any:
    """Синхронно выполняет SELECT и возвращает одно значение."""
    return _query_single_sync(query, params)