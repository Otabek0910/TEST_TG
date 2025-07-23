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
    """Сервис для импорта данных из Excel файлов (АДАПТИРОВАННЫЙ ИЗ СТАРОГО КОДА)"""
    
    @staticmethod
    def validate_excel_file(file_path: str) -> Dict[str, Any]:
        """Валидирует Excel файл и проверяет структуру"""
        try:
            if not os.path.exists(file_path):
                return {'valid': False, 'error': 'Файл не найден'}
            
            xls = pd.ExcelFile(file_path)
            sheet_names = xls.sheet_names
            
            expected_sheets = ['Дисциплины', 'Корпуса', 'Виды работ']
            found_sheets = []
            
            for sheet in expected_sheets:
                if sheet in sheet_names:
                    found_sheets.append(sheet)
            
            if not found_sheets:
                return {
                    'valid': False, 
                    'error': f'Не найдены ожидаемые листы: {", ".join(expected_sheets)}'
                }
            
            # Проверяем структуру каждого найденного листа
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
        """Валидирует структуру конкретного листа"""
        required_columns = {
            'Дисциплины': ['name'],
            'Корпуса': ['name'],
            'Виды работ': ['name', 'discipline_name']
        }
        
        optional_columns = {
            'Дисциплины': ['description'],
            'Корпуса': ['display_order'],
            'Виды работ': ['unit_of_measure', 'norm_per_unit']
        }
        
        if sheet_name not in required_columns:
            return {'valid': False, 'error': f'Неизвестный лист: {sheet_name}'}
        
        # Проверяем обязательные колонки
        required = required_columns[sheet_name]
        missing_columns = [col for col in required if col not in df.columns]
        
        if missing_columns:
            return {
                'valid': False,
                'error': f'Отсутствуют обязательные колонки: {", ".join(missing_columns)}'
            }
        
        # Проверяем данные
        empty_rows = df[required].isnull().all(axis=1).sum()
        total_rows = len(df)
        valid_rows = total_rows - empty_rows
        
        return {
            'valid': True,
            'total_rows': total_rows,
            'valid_rows': valid_rows,
            'empty_rows': empty_rows
        }
    
    @staticmethod
    def import_directories_from_excel(file_path: str) -> Dict[str, Any]:
        """Импортирует справочники из Excel файла (адаптировано из старого кода)"""
        counters = {'disciplines': 0, 'objects': 0, 'work_types': 0}
        errors = []
        
        # Сначала валидируем файл
        validation = ImportService.validate_excel_file(file_path)
        if not validation['valid']:
            return {
                'success': False,
                'error': validation['error'],
                'counters': counters
            }
        
        conn = None
        xls = None
        
        try:
            xls = pd.ExcelFile(file_path)
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            # 1. Обработка дисциплин (добавляем новые, не трогаем существующие)
            if 'Дисциплины' in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name='Дисциплины').dropna(subset=['name'])
                    added_count = 0
                    
                    for _, row in df.iterrows():
                        name = str(row['name']).strip()
                        description = str(row.get('description', '')).strip() if pd.notna(row.get('description')) else None
                        
                        if name:
                            cursor.execute(
                                "INSERT INTO disciplines (name, description) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING", 
                                (name, description)
                            )
                            if cursor.rowcount > 0:
                                added_count += 1
                    
                    counters['disciplines'] = added_count
                    logger.info(f"Дисциплины: добавлено {added_count} новых записей")
                    
                except Exception as e:
                    error_msg = f"Ошибка обработки дисциплин: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 2. Обработка корпусов (полная перезапись)
            if 'Корпуса' in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name='Корпуса').dropna(subset=['name'])
                    
                    # Очищаем таблицу
                    cursor.execute("TRUNCATE TABLE construction_objects RESTART IDENTITY CASCADE;")
                    
                    for idx, row in df.iterrows():
                        name = str(row['name']).strip()
                        display_order = int(row.get('display_order', idx)) if pd.notna(row.get('display_order')) else idx
                        
                        if name:
                            cursor.execute(
                                "INSERT INTO construction_objects (name, display_order) VALUES (%s, %s)", 
                                (name, display_order)
                            )
                    
                    counters['objects'] = len(df)
                    logger.info(f"Корпуса: создано {counters['objects']} записей")
                    
                except Exception as e:
                    error_msg = f"Ошибка обработки корпусов: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # 3. Обработка видов работ (полная перезапись с проверкой дисциплин)
            if 'Виды работ' in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name='Виды работ').dropna(subset=['name', 'discipline_name'])
                    
                    # Очищаем таблицу
                    cursor.execute("TRUNCATE TABLE work_types RESTART IDENTITY CASCADE;")
                    
                    # Получаем маппинг дисциплин
                    cursor.execute("SELECT id, name FROM disciplines")
                    disciplines_map = {name.upper(): disc_id for disc_id, name in cursor.fetchall()}
                    
                    added_count = 0
                    skipped_count = 0
                    
                    for index, row in df.iterrows():
                        work_name = str(row['name']).strip()
                        discipline_name = str(row['discipline_name']).strip()
                        unit = str(row.get('unit_of_measure', '')).strip() if pd.notna(row.get('unit_of_measure')) else None
                        norm = float(row.get('norm_per_unit', 0.0)) if pd.notna(row.get('norm_per_unit')) else 0.0
                        
                        discipline_id = disciplines_map.get(discipline_name.upper())
                        
                        if discipline_id and work_name:
                            cursor.execute(
                                """INSERT INTO work_types (name, discipline_id, unit_of_measure, norm_per_unit, display_order) 
                                   VALUES (%s, %s, %s, %s, %s)""",
                                (work_name, discipline_id, unit, norm, index)
                            )
                            if cursor.rowcount > 0:
                                added_count += 1
                        else:
                            skipped_count += 1
                            if not discipline_id:
                                logger.warning(f"Дисциплина '{discipline_name}' для вида работ '{work_name}' не найдена")
                    
                    counters['work_types'] = added_count
                    logger.info(f"Виды работ: создано {added_count} записей, пропущено {skipped_count}")
                    
                    if skipped_count > 0:
                        errors.append(f"Пропущено {skipped_count} видов работ из-за неизвестных дисциплин")
                    
                except Exception as e:
                    error_msg = f"Ошибка обработки видов работ: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
            
            # Коммитим изменения
            conn.commit()
            
            return {
                'success': True,
                'counters': counters,
                'errors': errors
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
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