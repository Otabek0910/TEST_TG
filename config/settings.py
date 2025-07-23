import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Telegram Bot
TOKEN = os.getenv("TOKEN")
OWNER_ID = os.getenv("OWNER_ID")

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# Web App
WEB_APP_URL = os.getenv("WEB_APP_URL")
REPORTS_GROUP_URL = "https://t.me/+OdHnUNt1WaZiMDY6"

# Проверка обязательных переменных
if not TOKEN or not DATABASE_URL or not WEB_APP_URL:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Переменные TOKEN, DATABASE_URL или WEB_APP_URL не заданы в .env файле!")

# Таймауты и лимиты
SESSION_TIMEOUT_SECONDS = 300
REPORTS_PER_PAGE = 5
NORM_PER_PERSON = 5
USERS_PER_PAGE = 10
ELEMENTS_PER_PAGE = 10
BACKUP_RETENTION_DAYS = 7

# Класс для объединения всех настроек
class Settings:
    TOKEN = TOKEN
    OWNER_ID = OWNER_ID
    DATABASE_URL = DATABASE_URL
    WEB_APP_URL = WEB_APP_URL
    REPORTS_GROUP_URL = REPORTS_GROUP_URL
    SESSION_TIMEOUT_SECONDS = SESSION_TIMEOUT_SECONDS

# Создаем экземпляр для импорта
settings = Settings()