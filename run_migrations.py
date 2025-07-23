import logging
from database.migrations import run_all_migrations
from database import db_manager # <--- ИСПРАВЛЕНО ЗДЕСЬ

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

if __name__ == "__main__":
    # Запускаем все миграции
    run_all_migrations()