# roster/models.py

from django.db import models
from django.contrib.auth.models import User

class Discipline(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название дисциплины")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Дисциплина"
        verbose_name_plural = "Дисциплины"
    
    def __str__(self):
        return self.name

class PersonnelRole(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название роли")
    discipline = models.ForeignKey(Discipline, on_delete=models.CASCADE, verbose_name="Дисциплина")
    display_order = models.IntegerField(default=0, verbose_name="Порядок отображения")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Роль персонала"
        verbose_name_plural = "Роли персонала"
        ordering = ['display_order', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.discipline.name})"

class Brigade(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    brigade_name = models.CharField(max_length=100, verbose_name="Название бригады")
    discipline = models.ForeignKey(Discipline, on_delete=models.CASCADE, verbose_name="Дисциплина")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Бригада"
        verbose_name_plural = "Бригады"
    
    def __str__(self):
        return f"{self.brigade_name} ({self.user.get_full_name()})"

class DailyRoster(models.Model):
    brigade = models.ForeignKey(Brigade, on_delete=models.CASCADE, verbose_name="Бригада")
    roster_date = models.DateField(verbose_name="Дата табеля")
    total_people = models.IntegerField(verbose_name="Общее количество людей")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Ежедневный табель"
        verbose_name_plural = "Ежедневные табели"
        unique_together = ['brigade', 'roster_date']
    
    def __str__(self):
        return f"Табель {self.brigade.brigade_name} на {self.roster_date}"

class DailyRosterDetail(models.Model):
    roster = models.ForeignKey(DailyRoster, on_delete=models.CASCADE, related_name='details', verbose_name="Табель")
    role = models.ForeignKey(PersonnelRole, on_delete=models.CASCADE, verbose_name="Роль")
    people_count = models.IntegerField(verbose_name="Количество людей")
    
    class Meta:
        verbose_name = "Детали табеля"
        verbose_name_plural = "Детали табелей"
        unique_together = ['roster', 'role']
    
    def __str__(self):
        return f"{self.role.name}: {self.people_count} чел."