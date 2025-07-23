#!/usr/bin/env python3
"""
Скрипт для запуска миграций БД
"""

import sys
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    try:
        from database.migrations import run_all_migrations
        
        print("🔄 Запуск миграций базы данных...")
        
        if run_all_migrations():
            print("✅ Все миграции выполнены успешно!")
            return 0
        else:
            print("❌ Некоторые миграции не удались. Проверьте логи.")
            return 1
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())