# roster/migrations/0001_initial.py

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Discipline',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название дисциплины')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Дисциплина',
                'verbose_name_plural': 'Дисциплины',
            },
        ),
        migrations.CreateModel(
            name='PersonnelRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Название роли')),
                ('display_order', models.IntegerField(default=0, verbose_name='Порядок отображения')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('discipline', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='roster.discipline', verbose_name='Дисциплина')),
            ],
            options={
                'verbose_name': 'Роль персонала',
                'verbose_name_plural': 'Роли персонала',
                'ordering': ['display_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Brigade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('brigade_name', models.CharField(max_length=100, verbose_name='Название бригады')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('discipline', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='roster.discipline', verbose_name='Дисциплина')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Бригада',
                'verbose_name_plural': 'Бригады',
            },
        ),
        migrations.CreateModel(
            name='DailyRoster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('roster_date', models.DateField(verbose_name='Дата табеля')),
                ('total_people', models.IntegerField(verbose_name='Общее количество людей')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('brigade', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='roster.brigade', verbose_name='Бригада')),
            ],
            options={
                'verbose_name': 'Ежедневный табель',
                'verbose_name_plural': 'Ежедневные табели',
            },
        ),
        migrations.CreateModel(
            name='DailyRosterDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('people_count', models.IntegerField(verbose_name='Количество людей')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='roster.personnelrole', verbose_name='Роль')),
                ('roster', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='details', to='roster.dailyroster', verbose_name='Табель')),
            ],
            options={
                'verbose_name': 'Детали табеля',
                'verbose_name_plural': 'Детали табелей',
            },
        ),
        migrations.AddConstraint(
            model_name='dailyrosterdetail',
            constraint=models.UniqueConstraint(fields=('roster', 'role'), name='unique_roster_role'),
        ),
        migrations.AddConstraint(
            model_name='dailyroster',
            constraint=models.UniqueConstraint(fields=('brigade', 'roster_date'), name='unique_brigade_date'),
        ),
    ]