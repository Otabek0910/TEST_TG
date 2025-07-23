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
    """Сервис для экспорта/импорта данных (АДАПТИРОВАННЫЙ ИЗ СТАРОГО КОДА)"""
    
    @staticmethod
    def create_temp_directory():
        """Создает временную директорию если не существует"""
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
    
    @staticmethod
    def export_reports_to_excel(user_id: str, filter_params: Dict[str, Any] = None) -> Optional[str]:
        """Экспорт отчетов в Excel (адаптировано из старого кода)"""
        try:
            ExportService.create_temp_directory()
            
            current_date_str = date.today().strftime('%Y-%m-%d')
            file_path = os.path.join(TEMP_DIR, f"reports_export_{user_id}_{current_date_str}.xlsx")
            
            engine = create_engine(DATABASE_URL)
            
            # CHANGED: Адаптируем запрос под новую схему БД
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
                JOIN disciplines d ON r.discipline_id = d.id
            """
            
            # Добавляем фильтры если есть
            where_conditions = []
            params = {}
            
            if filter_params:
                if filter_params.get('date_from'):
                    where_conditions.append("r.report_date >= :date_from")
                    params['date_from'] = filter_params['date_from']
                
                if filter_params.get('date_to'):
                    where_conditions.append("r.report_date <= :date_to") 
                    params['date_to'] = filter_params['date_to']
                
                if filter_params.get('discipline_name'):
                    where_conditions.append("d.name = :discipline_name")
                    params['discipline_name'] = filter_params['discipline_name']
                
                if filter_params.get('status'):
                    where_conditions.append("r.workflow_status = :status")
                    params['status'] = filter_params['status']
            
            if where_conditions:
                base_query += " WHERE " + " AND ".join(where_conditions)
            
            base_query += " ORDER BY r.created_at DESC"
            
            with engine.connect() as connection:
                df = pd.read_sql_query(text(base_query), connection, params=params)
                
                if df.empty:
                    logger.warning("Нет данных для экспорта отчетов")
                    return None
                
                # Форматируем даты
                date_columns = ['Дата', 'Создан', 'Подписан супервайзером', 'Подписан мастером', 'Подписан КИОК']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                        if df[col].dt.tz is not None:
                            df[col] = df[col].dt.tz_localize(None)
                
                # Записываем в Excel
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Отчеты', index=False)
                    
                    # Настраиваем ширину колонок
                    worksheet = writer.sheets['Отчеты']
                    for i, col in enumerate(df.columns):
                        if not df[col].empty:
                            max_len = df[col].astype(str).map(len).max()
                        else:
                            max_len = 0
                        column_len = max(max_len, len(col)) + 2
                        worksheet.set_column(i, i, min(column_len, 50))  # Ограничиваем максимальную ширину
                
                logger.info(f"Экспорт отчетов выполнен: {file_path}")
                return file_path
                
        except Exception as e:
            logger.error(f"Ошибка экспорта отчетов: {e}")
            return None
    
    @staticmethod
    def export_full_database_backup(user_id: str) -> Optional[str]:
        """Полный экспорт БД в Excel (адаптировано из старого кода)"""
        try:
            ExportService.create_temp_directory()
            
            current_date_str = date.today().strftime('%Y-%m-%d')
            file_path = os.path.join(TEMP_DIR, f"full_backup_{user_id}_{current_date_str}.xlsx")
            
            engine = create_engine(DATABASE_URL)
            table_names = ALL_TABLE_NAMES_FOR_BACKUP
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                with engine.connect() as connection:
                    for table_name in table_names:
                        # Проверяем существование таблицы
                        query_check_table = text("""
                            SELECT EXISTS (
                                SELECT FROM pg_tables 
                                WHERE schemaname = 'public' AND tablename = :table_name
                            )
                        """)
                        
                        if connection.execute(query_check_table, {'table_name': table_name}).scalar():
                            df = pd.read_sql_query(text(f"SELECT * FROM {table_name}"), connection)
                            
                            # Обработка timezone для reports
                            if table_name == 'reports':
                                timezone_cols = ['created_at', 'supervisor_signed_at', 'master_signed_at', 'kiok_signed_at']
                                for col in timezone_cols:
                                    if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
                                        if df[col].dt.tz is not None:
                                            df[col] = df[col].dt.tz_localize(None)
                            
                            df.to_excel(writer, sheet_name=table_name, index=False)
                            logger.info(f"Таблица {table_name} экспортирована")
                        else:
                            logger.warning(f"Таблица {table_name} не найдена в БД, пропущена в бэкапе")
            
            logger.info(f"Полный бэкап БД создан: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка создания полного бэкапа БД: {e}")
            return None
    
    @staticmethod
    def export_formatted_database(user_id: str) -> Optional[str]:
        """Экспорт БД с читаемыми названиями колонок (адаптировано из старого кода)"""
        try:
            ExportService.create_temp_directory()
            
            current_date_str = date.today().strftime('%Y-%m-%d')
            file_path = os.path.join(TEMP_DIR, f"formatted_db_{user_id}_{current_date_str}.xlsx")
            
            engine = create_engine(DATABASE_URL)
            table_names = ALL_TABLE_NAMES_FOR_BACKUP
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                with engine.connect() as connection:
                    for table_name in table_names:
                        query_check_table = text("""
                            SELECT EXISTS (
                                SELECT FROM pg_tables 
                                WHERE schemaname = 'public' AND tablename = :table_name
                            )
                        """)
                        
                        if connection.execute(query_check_table, {'table_name': table_name}).scalar():
                            df = pd.read_sql_query(text(f"SELECT * FROM {table_name}"), connection)
                            
                            # Форматируем DataFrame для читаемости
                            formatted_df = ExportService._format_dataframe_for_excel(df.copy(), table_name)
                            formatted_df.to_excel(writer, sheet_name=table_name, index=False)
                            
                            # Настраиваем ширину колонок
                            worksheet = writer.sheets[table_name]
                            for i, col in enumerate(formatted_df.columns):
                                if not formatted_df[col].empty:
                                    max_len = formatted_df[col].astype(str).map(len).max()
                                else:
                                    max_len = 0
                                column_len = max(max_len, len(col)) + 2
                                worksheet.set_column(i, i, min(column_len, 50))
            
            logger.info(f"Форматированный экспорт БД создан: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка создания форматированного экспорта: {e}")
            return None
    
    @staticmethod
    def _format_dataframe_for_excel(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
        """Приводит DataFrame в читаемый вид с учетом специфики каждой таблицы (из старого кода)"""
        
        # Универсальный mapping для переименования колонок
        rename_map = {
            'id': 'ID',
            'created_at': 'Время создания', 
            'user_id': 'ID пользователя',
            'first_name': 'Имя',
            'last_name': 'Фамилия', 
            'username': 'Username',
            'phone_number': 'Телефон',
            'language_code': 'Язык',
            'name': 'Название',
            'description': 'Описание',
            'display_order': 'Порядок сортировки',
            'discipline_id': 'ID дисциплины',
            'unit_of_measure': 'Единица измерения',
            'norm_per_unit': 'Норма на единицу',
            'level': 'Уровень',
            'is_active': 'Активен'
        }
        
        # Специфичные mappings для разных таблиц
        table_specific_maps = {
            'reports': {
                'report_date': 'Дата отчета',
                'brigade_name': 'Бригада',
                'corpus_name': 'Корпус', 
                'work_type_name': 'Вид работ',
                'workflow_status': 'Статус',
                'supervisor_signed_at': 'Подписан супервайзером',
                'master_signed_at': 'Подписан мастером',
                'kiok_signed_at': 'Подписан КИОК',
                'report_data': 'Данные отчета'
            },
            'brigades_reference': {
                'brigade_name': 'Название бригады',
                'supervisor_id': 'ID супервайзера', 
                'brigade_size': 'Размер бригады'
            },
            'daily_rosters': {
                'roster_date': 'Дата табеля',
                'brigade_user_id': 'ID бригадира',
                'total_people': 'Всего людей'
            }
        }
        
        # Применяем переименование
        final_rename_map = rename_map.copy()
        if table_name in table_specific_maps:
            final_rename_map.update(table_specific_maps[table_name])
        
        df = df.rename(columns=final_rename_map)
        
        # Форматируем статусы для читаемости
        if 'Статус' in df.columns:
            status_map = {
                'draft': 'Черновик',
                'pending_master': 'Ожидает мастера', 
                'pending_kiok': 'Ожидает КИОК',
                'approved': 'Утвержден',
                'rejected': 'Отклонен'
            }
            df['Статус'] = df['Статус'].map(status_map).fillna(df['Статус'])
        
        # Форматируем булевы значения
        bool_columns = ['Активен']
        for col in bool_columns:
            if col in df.columns:
                df[col] = df[col].map({True: 'Да', False: 'Нет'}).fillna(df[col])
        
        # Форматируем даты
        date_columns = [col for col in df.columns if 'дата' in col.lower() or 'время' in col.lower() or 'подписан' in col.lower()]
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if df[col].dt.tz is not None:
                    df[col] = df[col].dt.tz_localize(None)
        
        return df
    
    @staticmethod
    def generate_directories_template() -> Optional[str]:
        """Создает шаблон Excel для справочников (адаптировано из старого кода)"""
        try:
            ExportService.create_temp_directory()
            
            current_date_str = date.today().strftime('%Y-%m-%d')
            file_path = os.path.join(TEMP_DIR, f"directories_template_{current_date_str}.xlsx")
            
            engine = create_engine(DATABASE_URL)
            
            with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                with engine.connect() as connection:
                    # Дисциплины
                    disciplines_df = pd.read_sql_query(
                        text("SELECT name, description FROM disciplines ORDER BY name"), 
                        connection
                    )
                    disciplines_df.to_excel(writer, sheet_name='Дисциплины', index=False)
                    
                    # Корпуса
                    objects_df = pd.read_sql_query(
                        text("SELECT name, display_order FROM construction_objects ORDER BY display_order"), 
                        connection
                    )
                    objects_df.to_excel(writer, sheet_name='Корпуса', index=False)
                    
                    # Виды работ
                    work_types_df = pd.read_sql_query(
                        text("""
                            SELECT wt.name, d.name as discipline_name, wt.unit_of_measure, wt.norm_per_unit 
                            FROM work_types wt 
                            JOIN disciplines d ON wt.discipline_id = d.id 
                            ORDER BY d.name, wt.display_order
                        """), 
                        connection
                    )
                    work_types_df.to_excel(writer, sheet_name='Виды работ', index=False)
                    
                    # Добавляем инструкции в первый лист
                    workbook = writer.book
                    instructions_sheet = workbook.add_worksheet('Инструкция')
                    instructions = [
                        "ИНСТРУКЦИЯ ПО ИМПОРТУ СПРАВОЧНИКОВ:",
                        "",
                        "1. Дисциплины - добавляются новые записи (существующие не изменяются)",
                        "   Обязательные колонки: name",
                        "   Опциональные: description",
                        "",
                        "2. Корпуса - полная перезапись всех данных",
                        "   Обязательные колонки: name", 
                        "   Опциональные: display_order",
                        "",
                        "3. Виды работ - полная перезапись с проверкой дисциплин",
                        "   Обязательные колонки: name, discipline_name",
                        "   Опциональные: unit_of_measure, norm_per_unit",
                        "",
                        "ВАЖНО: Сохраните файл и отправьте боту для применения изменений."
                    ]
                    for i, instruction in enumerate(instructions):
                     instructions_sheet.write(i, 0, instruction)
                                        
                    # Настраиваем ширину колонок для всех листов
                    for sheet_name in writer.sheets:
                        worksheet = writer.sheets[sheet_name]
                        for i in range(10):  # Настраиваем первые 10 колонок
                            worksheet.set_column(i, i, 20)
            
            logger.info(f"Шаблон справочников создан: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Ошибка создания шаблона справочников: {e}")
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