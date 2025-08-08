# services/roster_service.py - ИСПРАВЛЕНИЯ

import logging
from datetime import date
from typing import Dict, Any, Optional, List
from database.queries import db_query, db_execute

logger = logging.getLogger(__name__)

class RosterService:
    """Сервис для управления табелями учета рабочего времени"""
    
    @staticmethod
    async def get_available_roles(user_id: str) -> List[Dict[str, Any]]:
        """Получает роли персонала для дисциплины бригадира"""
        try:
            # Получаем дисциплину бригадира
            brigade_info = await db_query(
                "SELECT discipline_id FROM brigades WHERE user_id = %s", 
                (user_id,)
            )
            
            if not brigade_info:
                logger.error(f"Бригадир {user_id} не найден в таблице brigades")
                return []
            
            discipline_id = brigade_info[0][0]
            if not discipline_id:
                logger.error(f"У бригадира {user_id} не указана дисциплина")
                return []
            
            # Получаем роли для этой дисциплины
            roles_raw = await db_query("""
                SELECT pr.id, pr.role_name, d.name as discipline_name
                FROM personnel_roles pr
                JOIN disciplines d ON pr.discipline_id = d.id
                WHERE pr.discipline_id = %s
                ORDER BY pr.display_order, pr.role_name
            """, (discipline_id,))
            
            if not roles_raw:
                logger.warning(f"Роли для дисциплины {discipline_id} не найдены")
                return []
            
            return [
                {
                    'id': role_id, 
                    'name': role_name,
                    'discipline': discipline_name
                } 
                for role_id, role_name, discipline_name in roles_raw
            ]
            
        except Exception as e:
            logger.error(f"Ошибка получения ролей для бригадира {user_id}: {e}")
            return []
    
    @staticmethod
    def parse_roles_input(input_text: str, available_roles: List[Dict[str, Any]]) -> Optional[Dict[str, int]]:
        """Парсит ввод пользователя с количеством ролей"""
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
        """Проверяет безопасность сохранения табеля"""
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            
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
        """Сохраняет табель в БД"""
        try:
            today_str = date.today().strftime('%Y-%m-%d')
            total_people_new = roster_summary['total']
            
            # Удаляем старый табель
            await db_execute("DELETE FROM daily_rosters WHERE brigade_user_id = %s AND roster_date = %s", (user_id, today_str))
            
            # FIXED: Используем правильное поле total_personnel
            roster_id_raw = await db_query(
                "INSERT INTO daily_rosters (roster_date, brigade_user_id, total_personnel) VALUES (%s, %s, %s) RETURNING id",
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
                    # FIXED: Используем правильное поле personnel_count
                    await db_execute(
                        "INSERT INTO daily_roster_details (roster_id, role_id, personnel_count) VALUES (%s, %s, %s)",
                        (roster_id, role_id, count)
                    )
            
            logger.info(f"✅ Табель для пользователя {user_id} успешно сохранен (ID: {roster_id})")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения табеля для пользователя {user_id}: {e}")
            return False
    
    @staticmethod
    async def force_save_with_reports_deletion(user_id: str, roster_summary: Dict[str, Any], brigade_name: str) -> bool:
        """Принудительно сохраняет табель, удаляя отчеты за день"""
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
                SELECT dr.id, dr.total_personnel, dr.roster_date
                FROM daily_rosters dr
                WHERE dr.brigade_user_id = %s AND dr.roster_date = %s
            """, (user_id, today_str))
            
            if roster_info:
                roster_id, total_people, roster_date = roster_info[0]
                
                # FIXED: Используем правильное поле personnel_count
                details_raw = await db_query("""
                    SELECT pr.role_name, drd.personnel_count
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