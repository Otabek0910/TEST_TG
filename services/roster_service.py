# services/roster_service.py

import logging
from datetime import date
from typing import Dict, Any, Optional, List
from database.queries import db_query, db_execute

logger = logging.getLogger(__name__)

class RosterService:
    """Сервис для управления табелями учета рабочего времени (АДАПТИРОВАННЫЙ ИЗ СТАРОГО КОДА)"""
    
    @staticmethod
    async def get_available_roles() -> List[Dict[str, Any]]:
        """Получает список доступных ролей персонала из БД"""
        try:
            roles_raw = await db_query("SELECT id, role_name FROM personnel_roles ORDER BY role_name")
            return [{'id': role_id, 'name': role_name} for role_id, role_name in roles_raw] if roles_raw else []
        except Exception as e:
            logger.error(f"Ошибка получения списка ролей: {e}")
            return []
    
    @staticmethod
    def parse_roles_input(input_text: str, available_roles: List[Dict[str, Any]]) -> Optional[Dict[str, int]]:
        """Парсит ввод пользователя с количеством ролей (адаптировано из старого кода)"""
        try:
            parsed_roles = {}
            lines = input_text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Ищем числа в конце строки
                parts = line.rsplit(' ', 1)
                if len(parts) != 2:
                    continue
                
                role_part, count_part = parts
                role_part = role_part.strip()
                
                try:
                    count = int(count_part)
                    if count <= 0:
                        continue
                except ValueError:
                    continue
                
                # Ищем соответствующую роль
                role_found = None
                for role in available_roles:
                    if role['name'].lower() in role_part.lower() or role_part.lower() in role['name'].lower():
                        role_found = role
                        break
                
                if role_found:
                    parsed_roles[role_found['name']] = count
            
            return parsed_roles if parsed_roles else None
            
        except Exception as e:
            logger.error(f"Ошибка парсинга ввода ролей: {e}")
            return None
    
    @staticmethod
    def calculate_roster_summary(parsed_roles: Dict[str, int]) -> Dict[str, Any]:
        """Подсчитывает общую сводку табеля"""
        total_people = sum(parsed_roles.values())
        return {
            'details': parsed_roles,
            'total': total_people
        }
    
    @staticmethod
    async def check_roster_safety(user_id: str, total_people_new: int, brigade_name: str) -> Dict[str, Any]:
        """Проверяет безопасность сохранения табеля (адаптировано из старого кода)"""
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            
            # CHANGED: Адаптируем под новую схему БД
            assigned_info = await db_query("""
                SELECT SUM(CAST(report_data->>'people_count' AS INTEGER)) 
                FROM reports 
                WHERE brigade_name = %s AND report_date = %s
            """, (brigade_name, today_str))
            
            total_assigned = assigned_info[0][0] or 0 if assigned_info else 0
            
            is_safe = total_people_new >= total_assigned
            reserve = total_people_new - total_assigned if is_safe else 0
            
            return {
                'is_safe': is_safe,
                'total_assigned': total_assigned,
                'reserve': reserve,
                'total_new': total_people_new
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки безопасности табеля: {e}")
            return {
                'is_safe': True,
                'total_assigned': 0,
                'reserve': total_people_new,
                'total_new': total_people_new
            }
    
    @staticmethod
    async def save_roster(user_id: str, roster_summary: Dict[str, Any]) -> bool:
        """Сохраняет табель в БД (адаптировано из старого кода)"""
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            total_people_new = roster_summary['total']
            
            # Удаляем старый табель, если он был (для чистоты)
            await db_execute("DELETE FROM daily_rosters WHERE brigade_user_id = %s AND roster_date = %s", (user_id, today_str))
            
            # Сохраняем "шапку" табеля
            roster_id_raw = await db_query(
                "INSERT INTO daily_rosters (roster_date, brigade_user_id, total_people) VALUES (%s, %s, %s) RETURNING id",
                (today_str, user_id, total_people_new)
            )
            
            if not roster_id_raw:
                logger.error("Не удалось создать запись в daily_rosters")
                return False
            
            roster_id = roster_id_raw[0][0]
            
            # Сохраняем детализацию
            roles_map_raw = await db_query("SELECT id, role_name FROM personnel_roles")
            roles_map = {name: role_id for role_id, name in roles_map_raw} if roles_map_raw else {}
            
            details_to_save = roster_summary.get('details', {})
            for role_name, count in details_to_save.items():
                role_id = roles_map.get(role_name)
                if role_id:
                    await db_execute(
                        "INSERT INTO daily_roster_details (roster_id, role_id, people_count) VALUES (%s, %s, %s)",
                        (roster_id, role_id, count)
                    )
            
            logger.info(f"✅ Табель для пользователя {user_id} успешно сохранен (ID: {roster_id})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения табеля для пользователя {user_id}: {e}")
            return False
    
    @staticmethod
    async def force_save_with_reports_deletion(user_id: str, roster_summary: Dict[str, Any], brigade_name: str) -> bool:
        """Принудительно сохраняет табель, удаляя отчеты за день (адаптировано из старого кода)"""
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            
            # Удаляем отчеты за день
            await db_execute("DELETE FROM reports WHERE brigade_name = %s AND report_date = %s", (brigade_name, today_str))
            
            
            # Сохраняем табель
            return await RosterService.save_roster(user_id, roster_summary)
            
        except Exception as e:
            logger.error(f"Ошибка принудительного сохранения табеля: {e}")
            return False
    
    @staticmethod
    async def get_roster_status(user_id: str) -> Dict[str, Any]:
        """Проверяет статус табеля на сегодня"""
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            
            roster_info = await db_query("""
                SELECT dr.id, dr.total_people, dr.roster_date
                FROM daily_rosters dr
                WHERE dr.brigade_user_id = %s AND dr.roster_date = %s
            """, (user_id, today_str))
            
            if roster_info:
                roster_id, total_people, roster_date = roster_info[0]
                
                # Получаем детали
                details_raw = await db_query("""
                    SELECT pr.role_name, drd.people_count
                    FROM daily_roster_details drd
                    JOIN personnel_roles pr ON drd.role_id = pr.id
                    WHERE drd.roster_id = %s
                """, (roster_id,))
                
                details = {role_name: count for role_name, count in details_raw} if details_raw else {}
                
                return {
                    'exists': True,
                    'roster_id': roster_id,
                    'total_people': total_people,
                    'details': details,
                    'date': roster_date
                }
            else:
                return {'exists': False}
                
        except Exception as e:
            logger.error(f"Ошибка получения статуса табеля для {user_id}: {e}")
            return {'exists': False}
    
    @staticmethod
    async def reset_roster(user_id: str) -> bool:
        """Удаляет табель на сегодня (для админов)"""
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            
            deleted_count = await db_execute("DELETE FROM daily_rosters WHERE brigade_user_id = %s AND roster_date = %s", (user_id, today_str))
            
            if deleted_count:
                logger.info(f"Табель для пользователя {user_id} на {today_str} успешно удален")
                return True
            else:
                logger.warning(f"Табель для пользователя {user_id} на {today_str} не найден")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка удаления табеля для {user_id}: {e}")
            return False
    
    @staticmethod
    async def get_roster_history(user_id: str, days: int = 7) -> List[Dict[str, Any]]:
        """Получает историю табелей пользователя"""
        try:
            history_raw = await db_query("""
                SELECT dr.roster_date, dr.total_people, dr.id
                FROM daily_rosters dr
                WHERE dr.brigade_user_id = %s 
                AND dr.roster_date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY dr.roster_date DESC
            """, (user_id, days))
            
            history = []
            for roster_date, total_people, roster_id in history_raw:
                # Получаем детали для каждого табеля
                details_raw = await db_query("""
                    SELECT pr.role_name, drd.people_count
                    FROM daily_roster_details drd
                    JOIN personnel_roles pr ON drd.role_id = pr.id
                    WHERE drd.roster_id = %s
                """, (roster_id,))
                
                details = {role_name: count for role_name, count in details_raw} if details_raw else {}
                
                history.append({
                    'date': roster_date,
                    'total_people': total_people,
                    'details': details
                })
            
            return history
            
        except Exception as e:
            logger.error(f"Ошибка получения истории табелей для {user_id}: {e}")
            return []