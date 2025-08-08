# roster/services.py

from django.db import transaction
from django.utils import timezone
from datetime import date
from typing import Dict, List, Any, Optional
import logging

from .models import PersonnelRole, DailyRoster, DailyRosterDetail, Brigade, Discipline

logger = logging.getLogger(__name__)

class RosterService:
    """Сервис для работы с табелями"""
    
    @staticmethod
    def get_available_roles(user_id: int) -> List[Dict[str, Any]]:
        """Получает роли персонала для дисциплины бригадира"""
        try:
            # Получаем бригаду пользователя
            brigade = Brigade.objects.select_related('discipline').get(user_id=user_id)
            
            # Получаем роли для этой дисциплины
            roles = PersonnelRole.objects.filter(
                discipline=brigade.discipline
            ).order_by('display_order', 'name')
            
            return [
                {
                    'id': role.id,
                    'name': role.name,
                    'discipline': brigade.discipline.name
                }
                for role in roles
            ]
            
        except Brigade.DoesNotExist:
            logger.error(f"Бригадир с user_id {user_id} не найден")
            return []
        except Exception as e:
            logger.error(f"Ошибка получения ролей для {user_id}: {e}")
            return []
    
    @staticmethod
    def get_today_roster(user_id: int) -> Optional[Dict[str, Any]]:
        """Получает табель на сегодня"""
        try:
            brigade = Brigade.objects.get(user_id=user_id)
            today = date.today()
            
            roster = DailyRoster.objects.prefetch_related(
                'details__role'
            ).get(brigade=brigade, roster_date=today)
            
            details = {}
            for detail in roster.details.all():
                details[detail.role.name] = detail.people_count
            
            return {
                'total': roster.total_people,
                'details': details,
                'date': today.strftime('%Y-%m-%d')
            }
            
        except (Brigade.DoesNotExist, DailyRoster.DoesNotExist):
            return None
        except Exception as e:
            logger.error(f"Ошибка получения табеля для {user_id}: {e}")
            return None
    
    @staticmethod
    def calculate_roster_summary(parsed_roles: Dict[str, int]) -> Dict[str, Any]:
        """Вычисляет сводку табеля"""
        total = sum(parsed_roles.values())
        return {
            'total': total,
            'details': parsed_roles,
            'date': date.today().strftime('%Y-%m-%d')
        }
    
    @staticmethod
    @transaction.atomic
    def save_roster(user_id: int, roster_summary: Dict[str, Any]) -> bool:
        """Сохраняет табель в БД"""
        try:
            brigade = Brigade.objects.get(user_id=user_id)
            today = date.today()
            
            # Удаляем существующий табель за сегодня
            DailyRoster.objects.filter(
                brigade=brigade, 
                roster_date=today
            ).delete()
            
            # Создаем новый табель
            roster = DailyRoster.objects.create(
                brigade=brigade,
                roster_date=today,
                total_people=roster_summary['total']
            )
            
            # Сохраняем детали по ролям
            details_to_create = []
            for role_name, count in roster_summary['details'].items():
                try:
                    role = PersonnelRole.objects.get(
                        name=role_name,
                        discipline=brigade.discipline
                    )
                    details_to_create.append(
                        DailyRosterDetail(
                            roster=roster,
                            role=role,
                            people_count=count
                        )
                    )
                except PersonnelRole.DoesNotExist:
                    logger.warning(f"Роль {role_name} не найдена для дисциплины {brigade.discipline.name}")
            
            DailyRosterDetail.objects.bulk_create(details_to_create)
            
            logger.info(f"Табель для бригады {brigade.brigade_name} сохранен успешно")
            return True
            
        except Brigade.DoesNotExist:
            logger.error(f"Бригада для пользователя {user_id} не найдена")
            return False
        except Exception as e:
            logger.error(f"Ошибка сохранения табеля для {user_id}: {e}")
            return False
    
    @staticmethod
    def check_roster_safety(user_id: int, date_str: str) -> Dict[str, Any]:
        """Проверяет безопасность изменения табеля (заглушка для Django)"""
        # В Django версии упрощаем - просто разрешаем сохранение
        return {
            'safe': True,
            'total_assigned': 0
        }