# roster/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Discipline, PersonnelRole, Brigade, DailyRoster, DailyRosterDetail

@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at', 'roles_count']
    search_fields = ['name']
    readonly_fields = ['created_at']
    
    def roles_count(self, obj):
        count = obj.personnelrole_set.count()
        return format_html('<span style="color: #007cba; font-weight: bold;">{}</span>', count)
    roles_count.short_description = 'Количество ролей'

@admin.register(PersonnelRole)
class PersonnelRoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'discipline', 'display_order', 'created_at']
    list_filter = ['discipline', 'created_at']
    search_fields = ['name', 'discipline__name']
    list_editable = ['display_order']
    ordering = ['discipline', 'display_order', 'name']
    readonly_fields = ['created_at']

@admin.register(Brigade)
class BrigadeAdmin(admin.ModelAdmin):
    list_display = ['brigade_name', 'user_full_name', 'discipline', 'created_at', 'rosters_count']
    list_filter = ['discipline', 'created_at']
    search_fields = ['brigade_name', 'user__first_name', 'user__last_name', 'user__username']
    readonly_fields = ['created_at']
    
    def user_full_name(self, obj):
        full_name = obj.user.get_full_name()
        return full_name if full_name else obj.user.username
    user_full_name.short_description = 'Бригадир'
    
    def rosters_count(self, obj):
        count = obj.dailyroster_set.count()
        return format_html('<span style="color: #28a745; font-weight: bold;">{}</span>', count)
    rosters_count.short_description = 'Количество табелей'

class DailyRosterDetailInline(admin.TabularInline):
    model = DailyRosterDetail
    extra = 0
    readonly_fields = ['role', 'people_count']

@admin.register(DailyRoster)
class DailyRosterAdmin(admin.ModelAdmin):
    list_display = ['roster_date', 'brigade_name', 'discipline', 'total_people', 'details_count', 'created_at']
    list_filter = ['roster_date', 'brigade__discipline', 'created_at']
    search_fields = ['brigade__brigade_name', 'brigade__user__first_name', 'brigade__user__last_name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [DailyRosterDetailInline]
    date_hierarchy = 'roster_date'
    
    def brigade_name(self, obj):
        return obj.brigade.brigade_name
    brigade_name.short_description = 'Бригада'
    
    def discipline(self, obj):
        return obj.brigade.discipline.name
    discipline.short_description = 'Дисциплина'
    
    def details_count(self, obj):
        count = obj.details.count()
        return format_html('<span style="color: #17a2b8; font-weight: bold;">{}</span>', count)
    details_count.short_description = 'Ролей в табеле'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'brigade__user', 'brigade__discipline'
        ).prefetch_related('details')

@admin.register(DailyRosterDetail)
class DailyRosterDetailAdmin(admin.ModelAdmin):
    list_display = ['roster_info', 'role_name', 'people_count', 'discipline']
    list_filter = ['roster__roster_date', 'role__discipline', 'roster__brigade__discipline']
    search_fields = ['role__name', 'roster__brigade__brigade_name']
    readonly_fields = ['roster_info', 'discipline']
    
    def roster_info(self, obj):
        return f"{obj.roster.brigade.brigade_name} - {obj.roster.roster_date}"
    roster_info.short_description = 'Табель'
    
    def role_name(self, obj):
        return obj.role.name
    role_name.short_description = 'Роль'
    
    def discipline(self, obj):
        return obj.role.discipline.name
    discipline.short_description = 'Дисциплина'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'roster__brigade__discipline', 'role__discipline'
        )