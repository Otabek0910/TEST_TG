# services/import_service.py

import logging
import os
import pandas as pd
import psycopg2
from typing import Dict, Any, Optional, Tuple

from config.settings import DATABASE_URL
from utils.constants import TEMP_DIR
from database.queries import db_query, db_execute

logger = logging.getLogger(__name__)

class ImportService:
    """Сервис для импорта данных из Excel файлов (УНИВЕРСАЛЬНАЯ ВЕРСИЯ)"""
    
    @staticmethod
    def validate_excel_file(file_path: str) -> Dict[str, Any]:
        """Валидирует Excel файл и проверяет структуру"""
        try:
            if not os.path.exists(file_path):
                return {'valid': False, 'error': 'Файл не найден'}
            
            xls = pd.ExcelFile(file_path)
            sheet_names = xls.sheet_names
            
            logger.info(f"DEBUG: Найденные листы в файле: {sheet_names}")
            
            if len(sheet_names) == 0:
                return {'valid': False, 'error': 'Excel файл не содержит листов'}
            
            # FIXED: Принимаем все листы
            found_sheets = sheet_names
            logger.info(f"DEBUG: Будем обрабатывать листы: {found_sheets}")
            
            # Проверяем структуру каждого листа
            validation_results = {}
            
            for sheet in found_sheets:
                try:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    validation_results[sheet] = ImportService._validate_sheet_structure(sheet, df)
                except Exception as e:
                    validation_results[sheet] = {
                        'valid': False,
                        'error': f'Ошибка чтения листа {sheet}: {str(e)}'
                    }
            
            xls.close()
            
            return {
                'valid': True,
                'found_sheets': found_sheets,
                'sheet_validations': validation_results
            }
            
        except Exception as e:
            logger.error(f"Ошибка валидации Excel файла: {e}")
            return {'valid': False, 'error': f'Ошибка чтения файла: {str(e)}'}
    
    @staticmethod
    def _validate_sheet_structure(sheet_name: str, df: pd.DataFrame) -> Dict[str, Any]:
        """Валидирует структуру конкретного листа (УНИВЕРСАЛЬНАЯ)"""
        
        # FIXED: Универсальная валидация - проверяем есть ли данные
        if df.empty:
            return {'valid': False, 'error': f'Лист {sheet_name} пуст'}
        
        # Проверяем что есть хотя бы одна колонка с данными
        non_empty_cols = [col for col in df.columns if not df[col].isnull().all()]
        
        if not non_empty_cols:
            return {'valid': False, 'error': f'Лист {sheet_name} не содержит данных'}
        
        total_rows = len(df)
        empty_rows = df.isnull().all(axis=1).sum()
        valid_rows = total_rows - empty_rows
        
        return {
            'valid': True,
            'total_rows': total_rows,
            'valid_rows': valid_rows,
            'empty_rows': empty_rows,
            'columns': list(df.columns)
        }
    
    @staticmethod
    def import_directories_from_excel(file_path: str) -> Dict[str, Any]:
        """Импортирует справочники из Excel файла (УНИВЕРСАЛЬНАЯ ВЕРСИЯ)"""
        
        logger.info(f"DEBUG: Начинаем импорт из файла: {file_path}")
        counters = {'disciplines': 0, 'objects': 0, 'work_types': 0}
        errors = []
        
        # Валидируем файл
        validation = ImportService.validate_excel_file(file_path)
        if not validation['valid']:
            return {
                'success': False,
                'error': validation['error'],
                'counters': counters
            }
        
        logger.info(f"DEBUG: Найденные листы для импорта: {validation['found_sheets']}")
        
        conn = None
        xls = None
        cursor = None
        
        try:
            xls = pd.ExcelFile(file_path)
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            sheet_names = validation['found_sheets']
            
            # FIXED: Обрабатываем листы по порядку, пытаемся определить содержимое
            
            # 1. Ищем лист с дисциплинами (первый подходящий)
            disciplines_sheet = ImportService._find_disciplines_sheet(xls, sheet_names)
            if disciplines_sheet:
                try:
                    df = pd.read_excel(xls, sheet_name=disciplines_sheet)
                    logger.info(f"DEBUG: Обрабатываем дисциплины из листа '{disciplines_sheet}', строк: {len(df)}")
                    
                    added_count = 0
                    name_col = ImportService._find_name_column(df)
                    desc_col = ImportService._find_description_column(df)
                    
                    if name_col:
                        for _, row in df.iterrows():
                            name = str(row[name_col]).strip() if pd.notna(row[name_col]) else None
                            description = str(row[desc_col]).strip() if desc_col and pd.notna(row[desc_col]) else None
                            
                            if name and name.lower() not in ['nan', '']:
                                cursor.execute(
                                    "INSERT INTO disciplines (name, description) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING", 
                                    (name, description)
                                )
                                if cursor.rowcount > 0:
                                    added_count += 1
                        
                        counters['disciplines'] = added_count
                        logger.info(f"DEBUG: Дисциплин добавлено: {added_count}")
                    else:
                        logger.warning(f"Не найдена колонка с названиями в листе {disciplines_sheet}")
                        
                except Exception as e:
                    error_msg = f"Ошибка обработки дисциплин: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 2. Ищем лист с корпусами
            objects_sheet = ImportService._find_objects_sheet(xls, sheet_names)
            if objects_sheet:
                try:
                    df = pd.read_excel(xls, sheet_name=objects_sheet)
                    logger.info(f"DEBUG: Обрабатываем корпуса из листа '{objects_sheet}', строк: {len(df)}")
                    
                    # Очищаем таблицу
                    cursor.execute("TRUNCATE TABLE construction_objects RESTART IDENTITY CASCADE;")
                    
                    name_col = ImportService._find_name_column(df)
                    order_col = ImportService._find_order_column(df)
                    
                    added_count = 0
                    if name_col:
                        for idx, row in df.iterrows():
                            name = str(row[name_col]).strip() if pd.notna(row[name_col]) else None
                            display_order = int(row[order_col]) if order_col and pd.notna(row[order_col]) else idx
                            
                            if name and name.lower() not in ['nan', '']:
                                cursor.execute(
                                    "INSERT INTO construction_objects (name, display_order) VALUES (%s, %s)", 
                                    (name, display_order)
                                )
                                added_count += 1
                        
                        counters['objects'] = added_count
                        logger.info(f"DEBUG: Корпусов добавлено: {added_count}")
                    else:
                        logger.warning(f"Не найдена колонка с названиями в листе {objects_sheet}")
                        
                except Exception as e:
                    error_msg = f"Ошибка обработки корпусов: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 3. Ищем лист с видами работ
            work_types_sheet = ImportService._find_work_types_sheet(xls, sheet_names)
            if work_types_sheet:
                try:
                    df = pd.read_excel(xls, sheet_name=work_types_sheet)
                    logger.info(f"DEBUG: Обрабатываем виды работ из листа '{work_types_sheet}', строк: {len(df)}")
                    
                    # Очищаем таблицу
                    cursor.execute("TRUNCATE TABLE work_types RESTART IDENTITY CASCADE;")
                    
                    # Получаем маппинг дисциплин
                    cursor.execute("SELECT id, name FROM disciplines")
                    disciplines_map = {name.upper(): disc_id for disc_id, name in cursor.fetchall()}
                    
                    name_col = ImportService._find_name_column(df)
                    discipline_col = ImportService._find_discipline_column(df)
                    unit_col = ImportService._find_unit_column(df)
                    norm_col = ImportService._find_norm_column(df)
                    
                    added_count = 0
                    skipped_count = 0
                    
                    if name_col and discipline_col:
                        for index, row in df.iterrows():
                            work_name = str(row[name_col]).strip() if pd.notna(row[name_col]) else None
                            discipline_name = str(row[discipline_col]).strip() if pd.notna(row[discipline_col]) else None
                            unit = str(row[unit_col]).strip() if unit_col and pd.notna(row[unit_col]) else None
                            norm = float(row[norm_col]) if norm_col and pd.notna(row[norm_col]) else 0.0
                            
                            if work_name and discipline_name and work_name.lower() not in ['nan', '']:
                                discipline_id = disciplines_map.get(discipline_name.upper())
                                
                                if discipline_id:
                                    cursor.execute(
                                        """INSERT INTO work_types (name, discipline_id, unit_of_measure, norm_per_unit, display_order) 
                                           VALUES (%s, %s, %s, %s, %s)""",
                                        (work_name, discipline_id, unit, norm, index)
                                    )
                                    added_count += 1
                                else:
                                    skipped_count += 1
                                    logger.warning(f"Дисциплина '{discipline_name}' для вида работ '{work_name}' не найдена")
                            else:
                                skipped_count += 1
                        
                        counters['work_types'] = added_count
                        logger.info(f"DEBUG: Видов работ добавлено: {added_count}, пропущено: {skipped_count}")
                        
                        if skipped_count > 0:
                            errors.append(f"Пропущено {skipped_count} видов работ")
                    else:
                        error_msg = f"Не найдены обязательные колонки в листе {work_types_sheet}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        
                except Exception as e:
                    error_msg = f"Ошибка обработки видов работ: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # Коммитим изменения
            conn.commit()
            logger.info("DEBUG: Транзакция успешно закоммичена")
            
            return {
                'success': True,
                'counters': counters,
                'errors': errors
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
                logger.error("DEBUG: Транзакция откачена из-за ошибки")
            error_msg = f"Критическая ошибка импорта: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'counters': counters
            }
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            if xls:
                xls.close()
    
    # HELPER METHODS для определения листов и колонок
    
    @staticmethod
    def _find_disciplines_sheet(xls, sheet_names):
        """Находит лист с дисциплинами"""
        keywords = ['дисциплин', 'discipline', 'отдел', 'department']
        for sheet in sheet_names:
            if any(keyword in sheet.lower() for keyword in keywords):
                return sheet
        return sheet_names[0] if sheet_names else None
    
    @staticmethod
    def _find_objects_sheet(xls, sheet_names):
        """Находит лист с корпусами/объектами"""
        keywords = ['корпус', 'объект', 'object', 'building', 'construction']
        for sheet in sheet_names:
            if any(keyword in sheet.lower() for keyword in keywords):
                return sheet
        return sheet_names[1] if len(sheet_names) > 1 else None
    
    @staticmethod
    def _find_work_types_sheet(xls, sheet_names):
        """Находит лист с видами работ"""
        keywords = ['работ', 'work', 'вид', 'type', 'activity']
        for sheet in sheet_names:
            if any(keyword in sheet.lower() for keyword in keywords):
                return sheet
        return sheet_names[2] if len(sheet_names) > 2 else None
    
    @staticmethod
    def _find_name_column(df):
        """Находит колонку с названиями"""
        keywords = ['name', 'название', 'наименование', 'имя', 'title']
        for col in df.columns:
            if any(keyword in str(col).lower() for keyword in keywords):
                return col
        return df.columns[0] if len(df.columns) > 0 else None
    
    @staticmethod
    def _find_description_column(df):
        """Находит колонку с описанием"""
        keywords = ['description', 'описание', 'комментарий', 'comment', 'note']
        for col in df.columns:
            if any(keyword in str(col).lower() for keyword in keywords):
                return col
        return None
    
    @staticmethod
    def _find_order_column(df):
        """Находит колонку с порядком"""
        keywords = ['order', 'порядок', 'display_order', 'sort']
        for col in df.columns:
            if any(keyword in str(col).lower() for keyword in keywords):
                return col
        return None
    
    @staticmethod
    def _find_discipline_column(df):
        """Находит колонку с дисциплиной"""
        keywords = ['discipline', 'дисциплина', 'отдел', 'department']
        for col in df.columns:
            if any(keyword in str(col).lower() for keyword in keywords):
                return col
        return None
    
    @staticmethod
    def _find_unit_column(df):
        """Находит колонку с единицами измерения"""
        keywords = ['unit', 'единица', 'measure', 'измерение']
        for col in df.columns:
            if any(keyword in str(col).lower() for keyword in keywords):
                return col
        return None
    
    @staticmethod
    def _find_norm_column(df):
        """Находит колонку с нормами"""
        keywords = ['norm', 'норма', 'rate', 'standard']
        for col in df.columns:
            if any(keyword in str(col).lower() for keyword in keywords):
                return col
        return None
    
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
    
    @staticmethod
    def format_import_summary(result: Dict[str, Any]) -> str:
        """Форматирует сводку результатов импорта"""
        if not result['success']:
            return f"❌ Ошибка импорта: {result.get('error', 'Неизвестная ошибка')}"
        
        counters = result['counters']
        errors = result.get('errors', [])
        
        summary_lines = [
            "✅ **Импорт справочников завершен**",
            "",
            "**Обновлено записей:**"
        ]
        
        if counters['disciplines'] > 0:
            summary_lines.append(f"  ▪️ Дисциплины: **{counters['disciplines']}** (добавлено новых)")
        
        if counters['objects'] > 0:
            summary_lines.append(f"  ▪️ Корпуса: **{counters['objects']}** (полностью перезаписано)")
        
        if counters['work_types'] > 0:
            summary_lines.append(f"  ▪️ Виды работ: **{counters['work_types']}** (полностью перезаписано)")
        
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
    def restore_database_from_excel(file_path: str) -> Dict[str, Any]:
        """Восстанавливает БД из Excel файла (полное восстановление)"""
        try:
            logger.info(f"DEBUG: Начинаем восстановление БД из файла: {file_path}")
            
            # Валидируем файл
            validation = ImportService.validate_excel_file(file_path)
            if not validation['valid']:
                return {'success': False, 'error': validation['error']}
            
            # Импортируем справочники (используем универсальную функцию)
            result = ImportService.import_directories_from_excel(file_path)
            
            logger.info(f"DEBUG: Результат восстановления: {result}")
            
            return {
                'success': result['success'],
                'restored_tables': ['disciplines', 'construction_objects', 'work_types'],
                'counters': result.get('counters', {}),
                'errors': result.get('errors', [])
            }
            
        except Exception as e:
            logger.error(f"Ошибка восстановления БД: {e}")
            return {'success': False, 'error': str(e)}