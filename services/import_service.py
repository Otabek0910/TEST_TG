# services/import_service.py

import logging
import os
import pandas as pd
from typing import Dict, List, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

from config.settings import DATABASE_URL
from utils.constants import TEMP_DIR, ALL_TABLE_NAMES_FOR_BACKUP

logger = logging.getLogger(__name__)

class ImportService:
    """Сервис импорта данных с универсальной UPSERT логикой"""
    
    @staticmethod
    def validate_excel_file(file_path: str) -> Dict[str, Any]:
        """Валидация Excel файла"""
        try:
            if not os.path.exists(file_path):
                return {'valid': False, 'error': 'Файл не найден'}
            
            if not file_path.endswith('.xlsx'):
                return {'valid': False, 'error': 'Поддерживаются только .xlsx файлы'}
            
            # Проверяем, что файл можно прочесть
            pd.read_excel(file_path, sheet_name=None, nrows=1)
            
            return {'valid': True}
            
        except Exception as e:
            return {'valid': False, 'error': f'Ошибка чтения файла: {str(e)}'}

    @staticmethod
    def _sync_table_from_dataframe(cursor, table_name: str, df: pd.DataFrame, 
                               id_column: str = 'id') -> Dict[str, int]:
     """Универсальная синхронизация таблицы из DataFrame"""
     result = {'inserted': 0, 'updated': 0, 'deleted': 0}
    
     if df.empty:
        # Если DataFrame пустой, очищаем таблицу
        cursor.execute(f"DELETE FROM {table_name}")
        result['deleted'] = cursor.rowcount
        return result
    
     # Проверяем существование ID столбца в таблице
     try:
         cursor.execute(f"SELECT {id_column} FROM {table_name} LIMIT 1")
     except Exception:
        # Если столбец не существует, пропускаем таблицу
        logger.warning(f"Столбец {id_column} не найден в таблице {table_name}, пропускаем")
        return result
    
     # Получаем список колонок (исключая id если он пустой)
     df_columns = [col for col in df.columns if col.lower() != id_column or not df[col].isna().all()]
    
     # Получаем существующие ID из БД
     cursor.execute(f"SELECT {id_column} FROM {table_name}")
     existing_ids = {str(row[0]) for row in cursor.fetchall()}  # Конвертируем в строки
    
     # ID из файла (только непустые)
     file_ids = set()
     for _, row in df.iterrows():
         if id_column in df.columns and pd.notna(row[id_column]):
             file_ids.add(str(row[id_column]))  # Конвертируем в строки
    
     # Удаляем записи, которых нет в файле
     ids_to_delete = existing_ids - file_ids
     if ids_to_delete:
         cursor.execute(f"DELETE FROM {table_name} WHERE {id_column} = ANY(%s)", 
                      (list(ids_to_delete),))
         result['deleted'] = cursor.rowcount
    
     # Обрабатываем каждую строку из файла
     for _, row in df.iterrows():
         # Проверяем, есть ли основные данные
         has_data = any(pd.notna(row[col]) and str(row[col]).strip() 
                      for col in df_columns if col.lower() != id_column)
        
         if not has_data:
             continue
            
         # Подготавливаем данные
         data = {}
         specified_id = None
        
         for col in df_columns:
            if col.lower() == id_column:
                if pd.notna(row[col]):
                    specified_id = str(row[col])  # Конвертируем в строку
                    data[col] = specified_id
            else:
                if pd.notna(row[col]):
                    data[col] = str(row[col]).strip()
                else:
                    data[col] = None
        
         if not data:
             continue
            
         # Формируем запрос
         columns = list(data.keys())
         values = list(data.values())
         placeholders = ', '.join(['%s'] * len(values))
        
         if specified_id and specified_id in existing_ids:
             # UPDATE существующей записи
             set_clause = ', '.join([f"{col} = %s" for col in columns if col.lower() != id_column])
             if set_clause:
                update_values = [v for k, v in data.items() if k.lower() != id_column]
                update_values.append(specified_id)
                cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE {id_column} = %s", 
                             update_values)
                if cursor.rowcount > 0:
                    result['updated'] += 1
         else:
             # INSERT новой записи
             columns_str = ', '.join(columns)
             cursor.execute(f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})", 
                         values)
             result['inserted'] += 1
    
     return result

    @staticmethod
    def import_directories_from_excel(file_path: str) -> Dict[str, Any]:
        """Импорт справочников (3 листа) с универсальной логикой"""
        conn = None
        counters = {'disciplines': 0, 'objects': 0, 'work_types': 0}
        errors = []
        
        try:
            logger.info(f"Начинаем импорт справочников из файла: {file_path}")
            
            # Валидация файла
            validation = ImportService.validate_excel_file(file_path)
            if not validation['valid']:
                return {'success': False, 'error': validation['error']}
            
            # Подключение к БД
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            # Читаем все листы
            try:
                xls = pd.ExcelFile(file_path)
                sheet_names = xls.sheet_names
                logger.info(f"Найдены листы: {sheet_names}")
            except Exception as e:
                return {'success': False, 'error': f'Ошибка чтения Excel файла: {str(e)}'}
            
            # 1. Обработка дисциплин
            disciplines_sheets = [s for s in sheet_names if 'дисциплин' in s.lower()]
            if disciplines_sheets:
                try:
                    df = pd.read_excel(xls, sheet_name=disciplines_sheets[0])
                    logger.info(f"Обрабатываем дисциплины из листа '{disciplines_sheets[0]}', строк: {len(df)}")
                    
                    # Синхронизируем с БД
                    result = ImportService._sync_table_from_dataframe(cursor, 'disciplines', df)
                    counters['disciplines'] = result['inserted'] + result['updated']
                    
                    logger.info(f"Дисциплины: добавлено {result['inserted']}, обновлено {result['updated']}, удалено {result['deleted']}")
                    
                except Exception as e:
                    error_msg = f"Ошибка обработки дисциплин: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 2. Обработка корпусов
            objects_sheets = [s for s in sheet_names if 'корпус' in s.lower()]
            if objects_sheets:
                try:
                    df = pd.read_excel(xls, sheet_name=objects_sheets[0])
                    logger.info(f"Обрабатываем корпуса из листа '{objects_sheets[0]}', строк: {len(df)}")
                    
                    result = ImportService._sync_table_from_dataframe(cursor, 'construction_objects', df)
                    counters['objects'] = result['inserted'] + result['updated']
                    
                    logger.info(f"Корпуса: добавлено {result['inserted']}, обновлено {result['updated']}, удалено {result['deleted']}")
                    
                except Exception as e:
                    error_msg = f"Ошибка обработки корпусов: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 3. Обработка видов работ (с проверкой дисциплин)
            work_types_sheets = [s for s in sheet_names if 'вид' in s.lower() and 'работ' in s.lower()]
            if work_types_sheets:
                try:
                    df = pd.read_excel(xls, sheet_name=work_types_sheets[0])
                    logger.info(f"Обрабатываем виды работ из листа '{work_types_sheets[0]}', строк: {len(df)}")
                    
                    # Получаем маппинг дисциплин
                    cursor.execute("SELECT id, name FROM disciplines")
                    disciplines_map = {name.upper(): disc_id for disc_id, name in cursor.fetchall()}
                    
                    # Обрабатываем виды работ с заменой discipline_name на discipline_id
                    if 'discipline_name' in df.columns:
                        df_processed = df.copy()
                        df_processed['discipline_id'] = df_processed['discipline_name'].apply(
                            lambda x: disciplines_map.get(str(x).upper()) if pd.notna(x) else None
                        )
                        # Удаляем discipline_name из обработки
                        df_processed = df_processed.drop(columns=['discipline_name'])
                        
                        # Фильтруем только строки с валидными дисциплинами
                        df_valid = df_processed[df_processed['discipline_id'].notna()]
                        
                        if len(df_valid) != len(df_processed):
                            skipped = len(df_processed) - len(df_valid)
                            errors.append(f"Пропущено {skipped} видов работ с невалидными дисциплинами")
                        
                        result = ImportService._sync_table_from_dataframe(cursor, 'work_types', df_valid)
                        counters['work_types'] = result['inserted'] + result['updated']
                        
                        logger.info(f"Виды работ: добавлено {result['inserted']}, обновлено {result['updated']}, удалено {result['deleted']}")
                    else:
                        error_msg = f"Не найден столбец discipline_name в листе {work_types_sheets[0]}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        
                except Exception as e:
                    error_msg = f"Ошибка обработки видов работ: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # Коммитим изменения
            conn.commit()
            logger.info("Транзакция успешно закоммичена")
            
            return {
                'success': True,
                'counters': counters,
                'errors': errors
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
                logger.error("Транзакция откачена из-за ошибки")
            error_msg = f"Критическая ошибка импорта: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'counters': counters
            }
        finally:
            if conn:
                conn.close()

    @staticmethod 
    def restore_full_database_from_excel(file_path: str) -> Dict[str, Any]:
        """Полное восстановление БД из Excel (все таблицы) - ИСПРАВЛЕНО"""
        conn = None
        restored_tables = []
        errors = []
        
        try:
            logger.info(f"Начинаем полное восстановление БД из файла: {file_path}")
            
            # Валидация файла
            validation = ImportService.validate_excel_file(file_path)
            if not validation['valid']:
                return {'success': False, 'error': validation['error']}
            
            # Подключение к БД
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            # FIXED: Отключаем проверки внешних ключей
            cursor.execute("SET session_replication_role = replica;")
            logger.info("Проверки внешних ключей отключены")
            
            # Читаем все листы
            try:
                xls = pd.ExcelFile(file_path)
                sheet_names = xls.sheet_names
                logger.info(f"Найдены листы для восстановления: {sheet_names}")
            except Exception as e:
                return {'success': False, 'error': f'Ошибка чтения Excel файла: {str(e)}'}
            
            # ВАЖНО: Порядок восстановления (зависимости)
            table_order = [
                'disciplines', 'construction_objects', 'personnel_roles',
                'admins', 'managers', 'supervisors', 'masters', 'brigades',
                'pto', 'kiok', 'work_types', 'brigades_reference',
                'reports', 'daily_rosters', 'daily_roster_details', 
                'topic_mappings', 'scheduled_notifications'
            ]

            pk_map = {
                'admins': 'user_id',
                'managers': 'user_id', 
                'supervisors': 'user_id',
                'masters': 'user_id',
                'brigades': 'user_id',
                'pto': 'user_id',
                'kiok': 'user_id'
            }
            
            # Обрабатываем таблицы в правильном порядке
            for table_name in table_order:
                if table_name in sheet_names:
                    try:
                        df = pd.read_excel(xls, sheet_name=table_name)
                        logger.info(f"Восстанавливаем таблицу {table_name}, строк: {len(df)}")
                        
                        # Специальная обработка для work_types (заменяем discipline_name на discipline_id)
                        if table_name == 'work_types' and 'discipline_name' in df.columns:
                            cursor.execute("SELECT id, name FROM disciplines")
                            disciplines_map = {name.upper(): disc_id for disc_id, name in cursor.fetchall()}
                            
                            df['discipline_id'] = df['discipline_name'].apply(
                                lambda x: disciplines_map.get(str(x).upper()) if pd.notna(x) else None
                            )
                            df = df.drop(columns=['discipline_name'])
                            df = df[df['discipline_id'].notna()]  # Только валидные дисциплины
                        
                        id_column = pk_map.get(table_name, 'id')
                        # Синхронизируем с БД
                        result = ImportService._sync_table_from_dataframe(cursor, table_name, df, id_column)
                        restored_tables.append({
                            'table': table_name,
                            'inserted': result['inserted'],
                            'updated': result['updated'], 
                            'deleted': result['deleted']
                        })
                        
                        logger.info(f"Таблица {table_name}: добавлено {result['inserted']}, обновлено {result['updated']}, удалено {result['deleted']}")
                        
                    except Exception as e:
                        error_msg = f"Ошибка восстановления таблицы {table_name}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
            
            # FIXED: Включаем обратно проверки внешних ключей
            cursor.execute("SET session_replication_role = DEFAULT;")
            logger.info("Проверки внешних ключей включены обратно")
            
            # Коммитим изменения
            conn.commit()
            logger.info("Полное восстановление БД успешно завершено")
            
            return {
                'success': True,
                'restored_tables': restored_tables,
                'errors': errors
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
                logger.error("Транзакция восстановления БД откачена из-за ошибки")
            error_msg = f"Критическая ошибка восстановления БД: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'restored_tables': restored_tables
            }
        finally:
            if conn:
                # Убеждаемся что проверки включены
                try:
                    cursor = conn.cursor()
                    cursor.execute("SET session_replication_role = DEFAULT;")
                    conn.commit()
                except:
                    pass
                conn.close()

    @staticmethod
    def format_import_summary(result: Dict[str, Any]) -> str:
        """Форматирует сводку результатов импорта"""
        if not result['success']:
            return f"❌ Ошибка импорта: {result.get('error', 'Неизвестная ошибка')}"
        
        counters = result.get('counters', {})
        errors = result.get('errors', [])
        
        summary_lines = [
            "✅ **Импорт справочников завершен**",
            "",
            "**Обновлено записей:**"
        ]
        
        if counters.get('disciplines', 0) > 0:
            summary_lines.append(f"  ▪️ Дисциплины: **{counters['disciplines']}**")
        
        if counters.get('objects', 0) > 0:
            summary_lines.append(f"  ▪️ Корпуса: **{counters['objects']}**")
        
        if counters.get('work_types', 0) > 0:
            summary_lines.append(f"  ▪️ Виды работ: **{counters['work_types']}**")
        
        if not any(counters.values()):
            summary_lines.append("  ▪️ Новых данных не обнаружено")
        
        if errors:
            summary_lines.extend([
                "",
                "⚠️ **Предупреждения:**"
            ])
            for error in errors:
                summary_lines.append(f"  • {error}")
        
        return "\n".join(summary_lines)

    @staticmethod
    def format_restore_summary(result: Dict[str, Any]) -> str:
        """Форматирует сводку результатов полного восстановления БД"""
        if not result['success']:
            return f"❌ Ошибка восстановления БД: {result.get('error', 'Неизвестная ошибка')}"
        
        restored_tables = result.get('restored_tables', [])
        errors = result.get('errors', [])
        
        summary_lines = [
            "✅ **Полное восстановление БД завершено**",
            "",
            "**Восстановленные таблицы:**"
        ]
        
        total_operations = 0
        for table_info in restored_tables:
            table_name = table_info['table']
            inserted = table_info['inserted']
            updated = table_info['updated']
            deleted = table_info['deleted']
            total = inserted + updated
            total_operations += total
            
            if total > 0:
                summary_lines.append(f"  ▪️ {table_name}: **{total}** записей (добавлено: {inserted}, обновлено: {updated}, удалено: {deleted})")
        
        summary_lines.extend([
            "",
            f"**Всего обработано записей: {total_operations}**"
        ])
        
        if errors:
            summary_lines.extend([
                "",
                "⚠️ **Ошибки при восстановлении:**"
            ])
            for error in errors:
                summary_lines.append(f"  • {error}")
        
        return "\n".join(summary_lines)

    @staticmethod
    def cleanup_temp_file(file_path: str):
        """Удаляет временный файл"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Временный файл удален: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка удаления временного файла {file_path}: {e}")

    @staticmethod
    def create_temp_directory():
        """Создает временную директорию если не существует"""
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)