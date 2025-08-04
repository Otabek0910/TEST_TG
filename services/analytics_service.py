# services/analytics_service.py

import logging
import pandas as pd
import asyncio
from datetime import date
from typing import Dict, Any, Optional, List
from functools import partial
from sqlalchemy import create_engine, text

from config.settings import DATABASE_URL
from database.queries import db_query, db_execute

logger = logging.getLogger(__name__)

# --- СИНХРОННЫЕ HELPERS ДЛЯ PANDAS (для запуска в потоках) ---

def _run_pandas_query(query: str, params: dict) -> pd.DataFrame:
    """[БЛОКИРУЮЩАЯ] Выполняет SQL-запрос и возвращает DataFrame."""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            df = pd.read_sql_query(text(query), connection, params=params)
        return df
    except Exception as e:
        logger.error(f"Ошибка выполнения Pandas-запроса: {e}")
        return pd.DataFrame()

# --- ASYNC SERVICE METHODS ---

class AnalyticsService:
    """Сервис для аналитики и статистики отчетов (ПОЛНОСТЬЮ АСИНХРОННАЯ ВЕРСИЯ)"""

    @staticmethod
    async def get_discipline_dashboard_data(discipline_name: str, user_role: Dict[str, Any]) -> Dict[str, Any]:
        """Асинхронно собирает данные для дашборда дисциплины."""
        try:
            params = (discipline_name,)
            discipline_id_raw = await db_query("SELECT id FROM disciplines WHERE name = %s", params)
            disc_id = discipline_id_raw[0][0] if discipline_id_raw else None

            user_counts = {'brigades': 0, 'pto': 0, 'kiok': 0}
            if disc_id:
                brigade_count = await db_query("SELECT COUNT(*) FROM brigades WHERE discipline_id = %s", (disc_id,))
                pto_count = await db_query("SELECT COUNT(*) FROM pto WHERE discipline_id = %s", (disc_id,))
                kiok_count = await db_query("SELECT COUNT(*) FROM kiok WHERE discipline_id = %s", (disc_id,))
                user_counts['brigades'] = brigade_count[0][0] if brigade_count else 0
                user_counts['pto'] = pto_count[0][0] if pto_count else 0
                user_counts['kiok'] = kiok_count[0][0] if kiok_count else 0

            report_stats_raw = await db_query("""
                SELECT CASE workflow_status WHEN 'approved' THEN '1' WHEN 'rejected' THEN '-1' ELSE '0' END as status, COUNT(*)
                FROM reports r JOIN disciplines d ON r.discipline_id = d.id
                WHERE d.name = %s GROUP BY workflow_status
            """, params)
            # FIXED: Handle case where db_query returns None
            report_stats = {str(status): count for status, count in (report_stats_raw or [])}

            today_str = date.today().strftime('%Y-%m-%d')
            all_brigades_q = await db_query("SELECT brigade_name FROM brigades WHERE discipline_id = %s", (disc_id,)) if disc_id else []
            # FIXED: Handle case where db_query returns None
            all_brigades = {row[0] for row in (all_brigades_q or [])}

            reported_today_raw = await db_query("""
                SELECT DISTINCT r.brigade_name FROM reports r JOIN disciplines d ON r.discipline_id = d.id
                WHERE d.name = %s AND r.report_date = %s
            """, params + (today_str,))
            # FIXED: Handle case where db_query returns None
            reported_today = {row[0] for row in (reported_today_raw or [])}

            analysis_data = {}
            if not user_role.get('isKiok'):
                analysis_data = await AnalyticsService._calculate_work_performance(discipline_name)

            low_performance_count = await AnalyticsService._get_low_performance_brigade_count(discipline_name)

            return {
                'report_stats': report_stats,
                'total_reports': sum(report_stats.values()),
                'non_reporters_count': len(all_brigades - reported_today),
                'low_performance_count': low_performance_count,
                'analysis_data': analysis_data,
                'user_counts': user_counts
            }
        except Exception as e:
            logger.error(f"Ошибка сбора данных дашборда для {discipline_name}: {e}")
            return {}

    @staticmethod
    async def get_hr_report_data(discipline_id: int, selected_date: date) -> Optional[Dict[str, Any]]:
        """Асинхронно собирает данные для HR-отчета."""
        date_str = selected_date.strftime('%Y-%m-%d')

        disc_name_raw = await db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,))
        if not disc_name_raw: return None

        summary_q = await db_query("""
            SELECT pr.role_name, SUM(drd.personnel_count) as total_by_role
            FROM daily_roster_details drd
            JOIN daily_rosters dr ON drd.roster_id = dr.id
            JOIN personnel_roles pr ON drd.role_id = pr.id
            JOIN brigades b ON dr.brigade_user_id = b.user_id
            WHERE dr.roster_date = %s AND b.discipline_id = %s
            GROUP BY pr.role_name ORDER BY pr.role_name;
        """, (date_str, discipline_id))

        brigades_count_q = await db_query("""
            SELECT COUNT(DISTINCT dr.brigade_user_id) FROM daily_rosters dr
            JOIN brigades b ON dr.brigade_user_id = b.user_id
            WHERE dr.roster_date = %s AND b.discipline_id = %s
        """, (date_str, discipline_id))
        
        # FIXED: Handle case where db_query returns None
        total_people = sum(item[1] for item in (summary_q or []))

        return {
            "discipline_name": disc_name_raw[0][0],
            "roster_data": summary_q or [],
            "total_people": total_people,
            "brigades_count": brigades_count_q[0][0] if brigades_count_q else 0
        }

    @staticmethod
    async def get_problem_brigades_data(selected_date: date, user_role: Dict[str, Any]) -> Dict[str, List]:
        """Асинхронно собирает данные о проблемных бригадах."""
        logger.info("Функция get_problem_brigades_data вызвана, но пока не реализована.")
        return {"non_reporters": [], "low_performers": []}

    @staticmethod
    async def get_foreman_performance_data(user_role: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Асинхронно собирает данные о производительности бригадиров."""
        logger.info("Функция get_foreman_performance_data вызвана, но пока не реализована.")
        return []
    
    @staticmethod
    async def _calculate_work_performance(discipline_name: str) -> Dict[str, Any]:
        """Асинхронный расчет статистики выработки."""
        loop = asyncio.get_running_loop()
        pd_query = """
            SELECT r.work_type_name, r.report_data->>'volume' as volume, 
                   r.report_data->>'people_count' as people_count, wt.norm_per_unit 
            FROM reports r 
            JOIN disciplines d ON r.discipline_id = d.id
            JOIN work_types wt ON d.id = wt.discipline_id AND r.work_type_name = wt.name 
            WHERE d.name = :discipline_name AND r.workflow_status = 'approved'
        """
        func = partial(_run_pandas_query, pd_query, {'discipline_name': discipline_name})
        df = await loop.run_in_executor(None, func)

        if df.empty:
            return {'overall_output_percent': 0, 'work_analysis': []}
        
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        df['people_count'] = pd.to_numeric(df['people_count'], errors='coerce').fillna(0)
        df['norm_per_unit'] = pd.to_numeric(df['norm_per_unit'], errors='coerce').fillna(0)
        df['planned_volume'] = df['people_count'] * df['norm_per_unit']
        
        overall_output_percent = (df['volume'].sum() / df['planned_volume'].sum()) * 100 if df['planned_volume'].sum() > 0 else 0
        
        work_summary = df.groupby('work_type_name').agg(
            total_volume=('volume', 'sum'), total_planned=('planned_volume', 'sum')
        ).reset_index()
        work_summary['avg_output'] = (work_summary['total_volume'] / work_summary['total_planned'].replace(0, 1)) * 100
        
        work_analysis = [row.to_dict() for _, row in work_summary.sort_values(by='avg_output', ascending=False).iterrows()]
        
        return {'overall_output_percent': overall_output_percent, 'work_analysis': work_analysis}

    @staticmethod
    async def _get_low_performance_brigade_count(discipline_name: str) -> int:
        """Асинхронный подсчет бригад с низкой выработкой."""
        loop = asyncio.get_running_loop()
        pd_query = """
            SELECT r.brigade_name, 
                   SUM(CAST(r.report_data->>'volume' AS NUMERIC)) as total_volume,
                   SUM(CAST(r.report_data->>'people_count' AS NUMERIC) * wt.norm_per_unit) as total_planned
            FROM reports r
            JOIN disciplines d ON r.discipline_id = d.id  
            JOIN work_types wt ON d.id = wt.discipline_id AND r.work_type_name = wt.name
            WHERE d.name = :discipline_name AND r.workflow_status = 'approved'
            GROUP BY r.brigade_name
            HAVING SUM(CAST(r.report_data->>'people_count' AS NUMERIC) * wt.norm_per_unit) > 0
        """
        func = partial(_run_pandas_query, pd_query, {'discipline_name': discipline_name})
        df = await loop.run_in_executor(None, func)

        if df.empty:
            return 0
        
        df['performance'] = (df['total_volume'] / df['total_planned']) * 100
        return len(df[df['performance'] < 100])

    @staticmethod
    async def get_overall_statistics() -> Dict[str, Any]:
        """Асинхронное получение общей статистики."""
        try:
            report_stats_raw = await db_query("""
                SELECT CASE workflow_status WHEN 'approved' THEN '1' WHEN 'rejected' THEN '-1' ELSE '0' END as status, COUNT(*)
                FROM reports GROUP BY workflow_status
            """)
            # FIXED: Handle case where db_query returns None
            report_stats = {str(status): count for status, count in (report_stats_raw or [])}
            
            today_str = date.today().strftime('%Y-%m-%d')
            all_brigades_count = await db_query("SELECT COUNT(*) FROM brigades WHERE is_active = true")
            total_brigades = all_brigades_count[0][0] if all_brigades_count else 0
            
            reported_today_count = await db_query("SELECT COUNT(DISTINCT brigade_name) FROM reports WHERE report_date = %s", (today_str,))
            reported_count = reported_today_count[0][0] if reported_today_count else 0
            
            discipline_analysis = await AnalyticsService._calculate_overall_discipline_performance()
            
            return {
                'report_stats': report_stats,
                'total_reports': sum(report_stats.values()),
                'non_reporters_count': total_brigades - reported_count,
                'discipline_analysis': discipline_analysis
            }
        except Exception as e:
            logger.error(f"Ошибка получения общей статистики: {e}")
            return {}

    @staticmethod
    async def _calculate_overall_discipline_performance() -> Dict[str, Any]:
        """Асинхронный расчет средней выработки по всем дисциплинам."""
        loop = asyncio.get_running_loop()
        pd_query = """
            SELECT d.name as discipline_name, 
                   CAST(r.report_data->>'volume' AS NUMERIC) as volume,
                   CAST(r.report_data->>'people_count' AS NUMERIC) as people_count, 
                   wt.norm_per_unit
            FROM reports r 
            JOIN disciplines d ON r.discipline_id = d.id
            JOIN work_types wt ON d.id = wt.discipline_id AND r.work_type_name = wt.name
            WHERE r.workflow_status = 'approved'
        """
        func = partial(_run_pandas_query, pd_query, {})
        df = await loop.run_in_executor(None, func)

        if df.empty:
            return {'overall_output_percent': 0, 'discipline_summary': []}
        
        df['planned_volume'] = pd.to_numeric(df['people_count']) * pd.to_numeric(df['norm_per_unit'])
        df['volume'] = pd.to_numeric(df['volume'])
        
        overall_output_percent = (df['volume'].sum() / df['planned_volume'].sum()) * 100 if df['planned_volume'].sum() > 0 else 0
        
        discipline_summary = df.groupby('discipline_name').apply(
            lambda x: (x['volume'].sum() / x['planned_volume'].sum()) * 100 if x['planned_volume'].sum() > 0 else 0
        ).reset_index(name='avg_output')
        
        return {
            'overall_output_percent': overall_output_percent,
            'discipline_summary': [row.to_dict() for _, row in discipline_summary.sort_values(by='avg_output', ascending=False).iterrows()]
        }

    @staticmethod
    async def get_overview_dashboard_data(selected_date: date) -> Dict[str, Any]:
        """Асинхронное получение данных для обзорного дашборда."""
        loop = asyncio.get_running_loop()
        date_str = selected_date.strftime('%Y-%m-%d')
        pd_query = """
            SELECT d.name as discipline_name,
                   CAST(r.report_data->>'people_count' AS NUMERIC) as people_count,
                   CAST(r.report_data->>'volume' AS NUMERIC) as volume,
                   wt.norm_per_unit,
                   CASE WHEN LOWER(r.work_type_name) LIKE '%прочие%' OR wt.norm_per_unit IS NULL 
                        THEN true ELSE false END as is_other
            FROM reports r
            JOIN disciplines d ON r.discipline_id = d.id
            LEFT JOIN work_types wt ON d.id = wt.discipline_id AND r.work_type_name = wt.name
            WHERE r.report_date = :report_date AND r.workflow_status = 'approved'
        """
        func = partial(_run_pandas_query, pd_query, {'report_date': date_str})
        df = await loop.run_in_executor(None, func)

        discipline_data = []
        if not df.empty:
            for discipline in df['discipline_name'].unique():
                disc_df = df[df['discipline_name'] == discipline]
                main_df = disc_df[~disc_df['is_other']]
                other_df = disc_df[disc_df['is_other']]
                
                plan_volume = (main_df['people_count'] * main_df['norm_per_unit']).sum() if not main_df.empty else 0
                
                discipline_data.append({
                    'name': discipline,
                    'main_people': int(main_df['people_count'].sum()),
                    'other_people': int(other_df['people_count'].sum()),
                    'performance': (main_df['volume'].sum() / plan_volume * 100) if plan_volume > 0 else 0,
                    'fact_volume': main_df['volume'].sum() if not main_df.empty else 0
                })
        
        return {'selected_date': selected_date, 'discipline_data': discipline_data}

    @staticmethod
    async def get_chart_data(discipline_id: int, selected_date: date) -> Optional[Dict[str, Any]]:
        """Асинхронное получение данных для графика."""
        discipline_name_raw = await db_query("SELECT name FROM disciplines WHERE id = %s", (discipline_id,))
        if not discipline_name_raw:
            return None
        
        loop = asyncio.get_running_loop()
        date_str = selected_date.strftime('%Y-%m-%d')
        pd_query = """
            SELECT r.work_type_name, 
                   CAST(r.report_data->>'people_count' AS NUMERIC) as people_count, 
                   CAST(r.report_data->>'volume' AS NUMERIC) as volume, 
                   wt.norm_per_unit
            FROM reports r
            LEFT JOIN work_types wt ON r.work_type_name = wt.name AND r.discipline_id = wt.discipline_id
            WHERE r.report_date = :report_date AND r.discipline_id = :discipline_id
        """
        params = {'report_date': date_str, 'discipline_id': discipline_id}
        func = partial(_run_pandas_query, pd_query, params)
        df = await loop.run_in_executor(None, func)

        if df.empty or df['norm_per_unit'].isnull().all():
            return None

        main_df = df[df['norm_per_unit'].notna() & ~df['work_type_name'].str.contains('Прочие', case=False, na=False)].copy()
        if main_df.empty:
            return None
        
        main_df['plan'] = main_df['people_count'] * main_df['norm_per_unit']
        df_chart = main_df.groupby('work_type_name').agg(
            plan=('plan', 'sum'), fact=('volume', 'sum'), people=('people_count', 'sum')
        ).reset_index()
        
        return {
            'discipline_name': discipline_name_raw[0][0],
            'selected_date': selected_date,
            'chart_data': [row.to_dict() for _, row in df_chart.iterrows()]
        }