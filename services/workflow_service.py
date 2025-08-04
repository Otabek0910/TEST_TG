# services/workflow_service.py

import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
import asyncio # CHANGED: Добавлен импорт
from functools import partial # CHANGED: Добавлен импорт

from database.queries import db_query, db_execute, db_query_single

logger = logging.getLogger(__name__)

class WorkflowStatus(Enum):
    DRAFT = "draft"
    PENDING_MASTER = "pending_master"
    PENDING_KIOK = "pending_kiok"
    APPROVED = "approved"
    REJECTED = "rejected"

    # --- СИНХРОННЫЙ HELPER ДЛЯ ФАЙЛОВ ---
def _save_file_sync(file_data: bytes, file_path: str):
    """[БЛОКИРУЮЩАЯ] Создает директорию и сохраняет файл."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'wb') as f:
        f.write(file_data)

class WorkflowService:
    """Сервис для управления жизненным циклом отчетов"""
    
    @staticmethod
    async def create_report(
        supervisor_id: str,
        discipline_id: int, # CHANGED
        report_data: Dict[str, Any]
    ) -> Optional[int]:
        """Создает новый отчет с использованием discipline_id."""
        try:
            # CHANGED: Запрос теперь вставляет discipline_id вместо discipline_name
            query = """
                SELECT r.*, 
                       s.supervisor_name, 
                       m.master_name,
                       k.kiok_name,
                       d.name as discipline_name
                FROM reports r
                LEFT JOIN supervisors s ON r.supervisor_id = s.user_id
                LEFT JOIN masters m ON r.master_id = m.user_id
                LEFT JOIN kiok k ON r.kiok_id = k.user_id
                LEFT JOIN disciplines d ON r.discipline_id = d.id
                WHERE r.id = %s
            """
            
            params = (
                supervisor_id,
                report_data.get('report_date'),
                report_data.get('brigade_name'),
                report_data.get('corpus_name'),
                discipline_id, # CHANGED
                report_data.get('work_type_name'),
                WorkflowStatus.PENDING_MASTER.value,
                json.dumps(report_data.get('details', {}))
            )
            
            report_id = await db_query_single(query, params)
            if report_id:
                logger.info(f"✅ Супервайзер {supervisor_id} создал отчет ID: {report_id}")
                return report_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания отчета: {e}")
        
        return None

    @staticmethod
    async def get_report_details(report_id: int) -> Optional[Dict[str, Any]]:
        """Получает полные детали отчета включая все подписи и вложения"""
        try:
            report_info_list = await db_query("""
                SELECT r.*, s.supervisor_name, m.master_name, k.kiok_name, d.name as discipline_name
                FROM reports r
                LEFT JOIN supervisors s ON r.supervisor_id = s.user_id
                LEFT JOIN masters m ON r.master_id = m.user_id
                LEFT JOIN kiok k ON r.kiok_id = k.user_id
                LEFT JOIN disciplines d ON r.discipline_id = d.id
                WHERE r.id = %s
            """, (report_id,), as_dict=True)
        
            if not report_info_list: return None
            
            report_dict = report_info_list[0]
            
            def safe_json_parse(field_value):
                if not isinstance(field_value, str): return field_value or {}
                try: return json.loads(field_value)
                except (json.JSONDecodeError, TypeError): return {}

            # FIXED: Удален нерабочий код. Теперь мы просто используем результат as_dict=True.
            report_dict['report_data'] = safe_json_parse(report_dict.get('report_data'))
            report_dict['kiok_attachments'] = safe_json_parse(report_dict.get('kiok_attachments'))
            
            return report_dict
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения деталей отчета {report_id}: {e}")
            return None
     
    @staticmethod
    async def submit_to_master(report_id: int, supervisor_id: str) -> bool:
        """Отправляет отчет мастеру на подтверждение"""
        try:
            # Проверяем, что отчет принадлежит супервайзеру
            check_query = "SELECT id FROM reports WHERE id = %s AND supervisor_id = %s AND workflow_status = %s"
            if not await db_query(check_query, (report_id, supervisor_id, WorkflowStatus.DRAFT.value)):
                return False
            
            # Обновляем статус
            update_query = """
                UPDATE reports 
                SET workflow_status = %s, supervisor_signed_at = NOW() 
                WHERE id = %s
            """
            
            return await db_execute(update_query, (WorkflowStatus.PENDING_MASTER.value, report_id))
            
        except Exception as e:
            logger.error(f"Ошибка отправки отчета мастеру: {e}")
            return False
    
    @staticmethod
    async def master_approve(report_id: int, master_id: str, signature_path: Optional[str] = None) -> bool:
        """Мастер подтверждает отчет"""
        try:
            # Проверяем права мастера
            master_check = await db_query(
                "SELECT discipline_id FROM masters WHERE user_id = %s AND can_approve_reports = true",
                (master_id,)
            )
            if not master_check:
                logger.warning(f"Мастер {master_id} не имеет прав на подтверждение")
                return False
            
            # Обновляем отчет
            update_query = """
                UPDATE reports 
                SET workflow_status = %s, master_id = %s, master_signed_at = NOW(), master_signature_path = %s
                WHERE id = %s AND workflow_status = %s
            """
            
            success = await db_execute(update_query, (
                WorkflowStatus.PENDING_KIOK.value, master_id, signature_path, 
                report_id, WorkflowStatus.PENDING_MASTER.value
            ))
            
            if success:
                logger.info(f"Отчет {report_id} подтвержден мастером {master_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка подтверждения мастером: {e}")
            return False
    
    @staticmethod
    async def master_reject(report_id: int, master_id: str, reason: str) -> bool:
        """Мастер отклоняет отчет"""
        try:
            # Добавляем причину отклонения в report_data
            report_data = await db_query("SELECT report_data FROM reports WHERE id = %s", (report_id,))
            if report_data:
                data = report_data[0][0] or {}
                data['master_rejection_reason'] = reason
                data['master_rejected_at'] = datetime.now().isoformat()
                
                update_query = """
                    UPDATE reports 
                    SET workflow_status = %s, master_id = %s, master_signed_at = NOW(), report_data = %s
                    WHERE id = %s AND workflow_status = %s
                """
                
                return await db_execute(update_query, (
                    WorkflowStatus.REJECTED.value, master_id, data,
                    report_id, WorkflowStatus.PENDING_MASTER.value
                ))
            
        except Exception as e:
            logger.error(f"Ошибка отклонения мастером: {e}")
        
        return False

    @staticmethod
    async def kiok_approve(report_id: int, kiok_id: str, inspection_number: str, 
                notes: str = "", attachments: List[str] = None) -> bool:
        """КИОК согласовывает отчет с номером инспекции (фото опционально)"""
        try:
            update_query = """
                UPDATE reports 
                SET workflow_status = %s, 
                    kiok_id = %s, 
                    kiok_signed_at = NOW(), 
                    kiok_inspection_number = %s, 
                    kiok_notes = %s,
                    kiok_attachments = %s
                WHERE id = %s AND workflow_status = %s
            """
        
            success = await db_execute(update_query, (
                WorkflowStatus.APPROVED.value, 
                kiok_id, 
                inspection_number,
                notes,
                json.dumps(attachments or []),
                report_id, 
                WorkflowStatus.PENDING_KIOK.value
            ))
        
            if success:
                logger.info(f"✅ КИОК {kiok_id} согласовал отчет {report_id} с номером инспекции {inspection_number}")
        
            return success
        
        except Exception as e:
            logger.error(f"❌ Ошибка согласования КИОК: {e}")
            return False
    
    @staticmethod
    async def kiok_reject(report_id: int, kiok_id: str, reason: str, 
                remark_file_path: str = None, attachments: List[str] = None) -> bool:
      """КИОК отклоняет отчет с замечаниями (может быть файл с фото внутри)"""
      try:
         update_query = """
                UPDATE reports 
                SET workflow_status = %s, 
                   kiok_id = %s, 
                 kiok_signed_at = NOW(),
                   kiok_notes = %s,
                    kiok_remark_document = %s, 
                    kiok_attachments = %s
                WHERE id = %s AND workflow_status = %s
            """
        
            # Добавляем детальную причину в report_data
         report_data = await db_query("SELECT report_data FROM reports WHERE id = %s", (report_id,))
         if report_data:
              data = json.loads(report_data[0][0]) if report_data[0][0] else {}
              data['kiok_rejection'] = {
                    'reason': reason,
                    'rejected_at': datetime.now().isoformat(),
                    'kiok_id': kiok_id,
                   'has_remark_file': bool(remark_file_path),
                    'attachments_count': len(attachments or [])
              }
            
              await db_execute("UPDATE reports SET report_data = %s WHERE id = %s", 
                         (json.dumps(data), report_id))
        
         success = await db_execute(update_query, (
                WorkflowStatus.REJECTED.value, 
                kiok_id, 
                reason,
                remark_file_path,
                json.dumps(attachments or []),
                report_id, 
             WorkflowStatus.PENDING_KIOK.value
          ))
        
         if success:
              logger.info(f"✅ КИОК {kiok_id} отклонил отчет {report_id} с замечаниями")
        
         return success
        
      except Exception as e:
           logger.error(f"❌ Ошибка отклонения КИОК: {e}")
           return False
    
    
    @staticmethod
    async def get_pending_reports_for_master(master_id: str) -> List[Dict[str, Any]]:
        """Получает отчеты, ожидающие подтверждения мастера, по discipline_id."""
        try:
            # CHANGED: Запрос теперь напрямую использует discipline_id мастера
            master_info = await db_query("SELECT discipline_id FROM masters WHERE user_id = %s", (master_id,))
            if not master_info or not master_info[0][0]:
                return []
            
            discipline_id = master_info[0][0]
            
            query = """
                SELECT id, supervisor_id, report_date, brigade_name, corpus_name, work_type_name
                FROM reports 
                WHERE workflow_status = %s AND discipline_id = %s
                ORDER BY created_at ASC
            """
            
            results = await db_query(query, (WorkflowStatus.PENDING_MASTER.value, discipline_id), as_dict=True)
            return results if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения отчетов для мастера: {e}")
            return []
    
    @staticmethod
    async def get_pending_reports_for_kiok(kiok_id: str) -> List[Dict[str, Any]]:
        """Получает отчеты, ожидающие согласования КИОК, по discipline_id."""
        try:
            # CHANGED: Запрос теперь напрямую использует discipline_id КИОК
            kiok_info = await db_query("SELECT discipline_id FROM kiok WHERE user_id = %s", (kiok_id,))
            if not kiok_info or not kiok_info[0][0]:
                return []
            
            discipline_id = kiok_info[0][0]
            
            query = """
                SELECT id, supervisor_id, report_date, brigade_name, corpus_name, work_type_name
                FROM reports 
                WHERE workflow_status = %s AND discipline_id = %s
                ORDER BY master_signed_at ASC
            """
            
            results = await db_query(query, (WorkflowStatus.PENDING_KIOK.value, discipline_id), as_dict=True)
            return results if results else []
            
        except Exception as e:
            logger.error(f"Ошибка получения отчетов для КИОК: {e}")
            return []
    @staticmethod
    async def can_user_approve_report(user_id: str, report_id: int, role: str) -> bool:
        """Проверяет, может ли пользователь подтвердить отчет, по discipline_id."""
        try:
            # CHANGED: Проверка теперь идет по discipline_id отчета
            report_info = await db_query("SELECT discipline_id, workflow_status FROM reports WHERE id = %s", (report_id,))
            if not report_info: return False
            
            report_discipline_id, status = report_info[0]
            table_name = f"{role}s" # master -> masters, kiok -> kioks (предполагая такое имя таблицы)
            
            if role == 'kiok': table_name = 'kiok' # Исключение для КИОК

            if (role == 'master' and status == WorkflowStatus.PENDING_MASTER.value) or \
               (role == 'kiok' and status == WorkflowStatus.PENDING_KIOK.value):
                
                user_check = await db_query(
                    f"SELECT 1 FROM {table_name} WHERE user_id = %s AND discipline_id = %s",
                    (user_id, report_discipline_id)
                )
                return bool(user_check)
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки прав пользователя: {e}")
            return False
        
    @staticmethod
    async def get_supervisor_brigades(supervisor_id: str) -> List[str]:
       """Получает список бригад, закрепленных за супервайзером"""
       try:
           result = await db_query("SELECT brigade_ids FROM supervisors WHERE user_id = %s", (supervisor_id,))
           if result and result[0][0]:
               return result[0][0]  # PostgreSQL array field
           return []
       except Exception as e:
           logger.error(f"❌ Ошибка получения бригад супервайзера: {e}")
           return []

    @staticmethod
    async def save_file_attachment(file_data: bytes, filename: str, report_id: int, 
                            attachment_type: str = "kiok") -> Optional[str]:
        """[ASYNC] Сохраняет файл вложения и возвращает путь"""
        try:
            attachments_dir = f"attachments/reports/{report_id}/{attachment_type}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"{timestamp}_{filename.replace(' ', '_')}"
            file_path = os.path.join(attachments_dir, safe_filename)
            
            # FIXED: Выполняем блокирующую операцию в отдельном потоке
            loop = asyncio.get_running_loop()
            func = partial(_save_file_sync, file_data, file_path)
            await loop.run_in_executor(None, func)
            
            logger.info(f"✅ Сохранено вложение {attachment_type}: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения вложения: {e}")
            return None