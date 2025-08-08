# roster/views.py

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
import json
from datetime import date
from typing import Dict, List, Any, Optional

from .models import PersonnelRole, DailyRoster, DailyRosterDetail, Brigade, Discipline
from .services import RosterService

@login_required
def roster_form(request):
    """Форма подачи табеля"""
    user = request.user
    
    # Получаем роли для дисциплины пользователя
    available_roles = RosterService.get_available_roles(user.id)
    
    # Проверяем существующий табель
    existing_roster = RosterService.get_today_roster(user.id)
    
    context = {
        'available_roles': available_roles,
        'existing_roster': existing_roster,
        'discipline_name': available_roles[0]['discipline'] if available_roles else 'Неизвестная',
        'today': date.today().strftime('%d.%m.%Y')
    }
    
    return render(request, 'roster/form.html', context)

@csrf_exempt
@login_required
def update_role_count(request):
    """AJAX обновление количества роли"""
    if request.method == 'POST':
        data = json.loads(request.body)
        role_id = data.get('role_id')
        action = data.get('action')  # 'increase' или 'decrease'
        
        # Получаем текущие данные из сессии
        roster_counts = request.session.get('roster_counts', {})
        
        current_count = roster_counts.get(str(role_id), 0)
        
        if action == 'increase' and current_count < 20:
            roster_counts[str(role_id)] = current_count + 1
        elif action == 'decrease' and current_count > 0:
            roster_counts[str(role_id)] = current_count - 1
        
        request.session['roster_counts'] = roster_counts
        
        # Подсчитываем общее количество
        total_people = sum(roster_counts.values())
        
        return JsonResponse({
            'success': True,
            'new_count': roster_counts.get(str(role_id), 0),
            'total_people': total_people
        })
    
    return JsonResponse({'success': False})

@csrf_exempt 
@login_required
def save_roster(request):
    """Сохранение табеля"""
    if request.method == 'POST':
        user = request.user
        roster_counts = request.session.get('roster_counts', {})
        
        if not any(count > 0 for count in roster_counts.values()):
            return JsonResponse({
                'success': False, 
                'error': 'Нужно указать хотя бы одну роль!'
            })
        
        # Формируем данные для сохранения
        parsed_roles = {}
        available_roles = RosterService.get_available_roles(user.id)
        
        for role in available_roles:
            count = roster_counts.get(str(role['id']), 0)
            if count > 0:
                parsed_roles[role['name']] = count
        
        # Сохраняем через сервис
        roster_summary = RosterService.calculate_roster_summary(parsed_roles)
        success = RosterService.save_roster(user.id, roster_summary)
        
        if success:
            # Очищаем сессию
            request.session.pop('roster_counts', None)
            return JsonResponse({
                'success': True,
                'message': 'Табель успешно сохранен!',
                'total_people': roster_summary['total']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Ошибка сохранения'
            })
    
    return JsonResponse({'success': False})

@login_required
def clear_roster(request):
    """Очистка табеля"""
    request.session.pop('roster_counts', None)
    return JsonResponse({'success': True})