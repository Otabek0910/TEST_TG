# main/urls.py

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def home_view(request):
    """Главная страница"""
    return HttpResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Система управления строительными отчетами</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #2c3e50; }
            ul { list-style-type: none; padding: 0; }
            li { margin: 10px 0; }
            a { text-decoration: none; color: #3498db; font-size: 18px; }
            a:hover { color: #2980b9; }
        </style>
    </head>
    <body>
        <h1>🏗️ Система управления строительными отчетами</h1>
        <h2>Доступные разделы:</h2>
        <ul>
            <li><a href="/roster/">📋 Система табелей</a></li>
            <li><a href="/admin/">⚙️ Админ-панель</a></li>
        </ul>
        <hr>
        <p><em>Telegram бот работает параллельно с веб-интерфейсом</em></p>
    </body>
    </html>
    """)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('roster/', include('roster.urls')),
    path('', home_view, name='home'),
]