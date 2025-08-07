# services/export_service.py

import logging
import os
import pandas as pd
from datetime import date
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, text

from config.settings import DATABASE_URL
from utils.constants import ALL_TABLE_NAMES_FOR_BACKUP, TEMP_DIR

logger = logging.getLogger(__name__)

class ExportService:
    """Сервис для экспорта данных в Excel (ИСПРАВЛЕННАЯ ВЕРСИЯ)"""
    
    @staticmethod
    def create_temp_directory():
        """Создает временную директорию если не существует"""
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
    
    @staticmethod
    def generate_directories_template() -> Optional[str]:
        """Создает шаблон Excel для справочников с ID"""
        try:
            ExportService.create_temp_directory()
            
            current_date_str = date.today().strftime('%Y-%m-%d')
            file_path = os.path.join(TEMP_DIR, f"directories_template_{current_date_str}.xlsx")
            
            engine = create_engine(DATABASE_URL)
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                with engine.connect() as connection:
                    # Дисциплины с ID
                    disciplines_df = pd.read_sql_query(
                        text("SELECT id, name, description FROM disciplines ORDER BY id"), 
                        connection
                    )
                    disciplines_df.to_excel(writer, sheet_name='Дисциплины', index=False)
                    
                    # Корпуса с ID  
                    objects_df = pd.read_sql_query(
                        text("SELECT id, name, display_order FROM construction_objects ORDER BY display_order"), 
                        connection
                    )
                    objects_df.to_excel(writer, sheet_name='Корпуса', index=False)
                    
                    # Виды работ с ID и discipline_name
                    work_types_df = pd.read_sql_query(
                        text("""
                            SELECT wt.id, wt.name, d.name as discipline_name, 
                                   wt.unit_of_measure, wt.norm_per_unit, wt.display_order
                            FROM work_types wt 
                            JOIN disciplines d ON wt.discipline_id = d.id 
                            ORDER BY d.name, wt.display_order
                        """), 
                        connection
                    )
                    work_types_df.to_excel(writer, sheet_name='Виды работ', index=False)
                    
                    # Инструкции
                    workbook = writer.book
                    instructions_sheet = workbook.add_worksheet('Инструкция')
                    instructions = [
                        "ИНСТРУКЦИЯ ПО ИМПОРТУ СПРАВОЧНИКОВ:",
                        "",
                        "1. ID - если указан, будет использован; если пустой - автогенерация",
                        "2. Строки не в файле будут УДАЛЕНЫ из БД",
                        "3. Столбцы читаются по заголовкам из этого файла",
                        "",
                        "Дисциплины: id, name, description",
                        "Корпуса: id, name, display_order", 
                        "Виды работ: id, name, discipline_name, unit_of_measure, norm_per_unit, display_order",
                        "",
                        "ВАЖНО: Сохраните файл и отправьте боту для применения изменений."
                    ]
                    for i, instruction in enumerate(instructions):
                        instructions_sheet.write(i, 0, instruction)
                                        
                    # Настраиваем ширину колонок
                    for sheet_name in writer.sheets:
                        worksheet = writer.sheets[sheet_name]
                        for i in range(10):
                            worksheet.set_column(i, i, 20)
            
            logger.info(f"Шаблон справочников создан: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка создания шаблона справочников: {e}")
            return None

    @staticmethod
    def export_full_database_backup(user_id: str) -> Optional[str]:
        """Полный экспорт БД с ID для восстановления"""
        try:
            ExportService.create_temp_directory()
            
            current_date_str = date.today().strftime('%Y-%m-%d')
            file_path = os.path.join(TEMP_DIR, f"full_db_backup_{user_id}_{current_date_str}.xlsx")
            
            engine = create_engine(DATABASE_URL)
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                with engine.connect() as connection:
                    
                    for table_name in ALL_TABLE_NAMES_FOR_BACKUP:
                        try:
                            # Проверяем существование таблицы
                            query_check_table = text("""
                                SELECT EXISTS (
                                    SELECT FROM pg_tables 
                                    WHERE schemaname = 'public' AND tablename = :table_name
                                )
                            """)
                            
                            if connection.execute(query_check_table, {'table_name': table_name}).scalar():
                                # Экспортируем с ID как первый столбец (если есть)
                                try:
                                    df = pd.read_sql_query(text(f"SELECT * FROM {table_name} ORDER BY id"), connection)
                                except Exception:
                                    # Если нет столбца id, экспортируем как есть
                                    df = pd.read_sql_query(text(f"SELECT * FROM {table_name}"), connection)
                                
                                # Обработка специфичных полей с датами/временем
                                if table_name == 'reports':
                                    timezone_cols = ['created_at', 'supervisor_signed_at', 'master_signed_at', 'kiok_signed_at']
                                    for col in timezone_cols:
                                        if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
                                            if df[col].dt.tz is not None:
                                                df[col] = df[col].dt.tz_localize(None)
                                
                                df.to_excel(writer, sheet_name=table_name, index=False)
                                logger.info(f"Экспортирована таблица {table_name}: {len(df)} записей")
                            else:
                                logger.warning(f"Таблица {table_name} не найдена в БД, пропущена в бэкапе")
                            
                        except Exception as e:
                            logger.error(f"Ошибка экспорта таблицы {table_name}: {e}")
                    
                    # Настраиваем ширину колонок
                    for sheet_name in writer.sheets:
                        worksheet = writer.sheets[sheet_name]
                        for i in range(20):
                            worksheet.set_column(i, i, 15)
            
            logger.info(f"Полный экспорт БД создан: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка полного экспорта БД: {e}")
            return None

    @staticmethod 
    def export_reports_to_excel(user_id: str, filter_params: Dict[str, Any] = None) -> Optional[str]:
        """Экспорт отчетов в Excel"""
        try:
            ExportService.create_temp_directory()
            
            current_date_str = date.today().strftime('%Y-%m-%d')
            file_path = os.path.join(TEMP_DIR, f"reports_export_{user_id}_{current_date_str}.xlsx")
            
            engine = create_engine(DATABASE_URL)
            
            base_query = """
                SELECT 
                    r.id as "ID отчета",
                    r.report_date as "Дата",
                    r.brigade_name as "Бригада", 
                    r.corpus_name as "Корпус",
                    d.name as "Дисциплина",
                    r.work_type_name as "Вид работ",
                    r.report_data->>'people_count' as "Кол-во людей",
                    r.report_data->>'volume' as "Объем",
                    r.report_data->>'notes' as "Примечания",
                    CASE r.workflow_status
                        WHEN 'approved' THEN 'Утвержден'
                        WHEN 'rejected' THEN 'Отклонен'
                        WHEN 'pending_master' THEN 'Ожидает мастера'
                        WHEN 'pending_kiok' THEN 'Ожидает КИОК'
                        ELSE 'Черновик'
                    END as "Статус",
                    r.created_at as "Создан",
                    r.supervisor_signed_at as "Подписан супервайзером",
                    r.master_signed_at as "Подписан мастером",
                    r.kiok_signed_at as "Подписан КИОК"
                FROM reports r
                LEFT JOIN disciplines d ON r.discipline_id = d.id
                WHERE 1=1
            """
            
            params = {}
            if filter_params:
                if filter_params.get('discipline_name'):
                    base_query += " AND d.name = %(discipline_name)s"
                    params['discipline_name'] = filter_params['discipline_name']
            
            base_query += " ORDER BY r.created_at DESC"
            
            with engine.connect() as connection:
                df = pd.read_sql_query(text(base_query), connection, params=params)
                
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Отчеты', index=False)
                    
                    # Настройка форматирования
                    workbook = writer.book
                    worksheet = writer.sheets['Отчеты']
                    
                    for i in range(len(df.columns)):
                        worksheet.set_column(i, i, 20)
            
            logger.info(f"Экспорт отчетов создан: {file_path}, записей: {len(df)}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка экспорта отчетов: {e}")
            return None

    @staticmethod
    def export_formatted_database(user_id: str) -> Optional[str]:
        """Экспорт БД с читаемыми названиями"""
        try:
            ExportService.create_temp_directory()
            
            current_date_str = date.today().strftime('%Y-%m-%d')
            file_path = os.path.join(TEMP_DIR, f"formatted_db_{user_id}_{current_date_str}.xlsx")
            
            engine = create_engine(DATABASE_URL)
            
            queries = {
                'Пользователи_Админы': "SELECT user_id as 'ID', first_name as 'Имя', last_name as 'Фамилия', username as 'Username', phone_number as 'Телефон', created_at as 'Создан' FROM admins",
                'Пользователи_Менеджеры': """
                    SELECT m.user_id as 'ID', m.first_name as 'Имя', m.last_name as 'Фамилия', 
                           m.username as 'Username', m.phone_number as 'Телефон',
                           m.level as 'Уровень', d.name as 'Дисциплина', m.created_at as 'Создан'
                    FROM managers m 
                    LEFT JOIN disciplines d ON m.discipline = d.id
                """,
                'Отчеты': """
                    SELECT r.id as 'ID', r.report_date as 'Дата', r.brigade_name as 'Бригада',
                           r.corpus_name as 'Корпус', d.name as 'Дисциплина', r.work_type_name as 'Вид работ',
                           r.workflow_status as 'Статус', r.created_at as 'Создан'
                    FROM reports r
                    LEFT JOIN disciplines d ON r.discipline_id = d.id
                """
            }
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                with engine.connect() as connection:
                    for sheet_name, query in queries.items():
                        try:
                            df = pd.read_sql_query(text(query), connection)
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            
                            # Форматирование
                            worksheet = writer.sheets[sheet_name]
                            for i in range(len(df.columns)):
                                worksheet.set_column(i, i, 18)
                                
                        except Exception as e:
                            logger.error(f"Ошибка экспорта листа {sheet_name}: {e}")
            
            logger.info(f"Форматированный экспорт БД создан: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка форматированного экспорта БД: {e}")
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