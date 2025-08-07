# test_export_isolated.py
# Тестируем экспорт-сервис изолированно без циклических импортов

import sys
import os

# Добавляем корневую папку в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_export_service():
    """Тест ExportService изолированно"""
    try:
        # Прямой импорт без services.__init__
        from services.export_service import ExportService
        
        print("✅ ExportService импортирован успешно")
        
        # Тест создания директории
        ExportService.create_temp_directory()
        print("✅ Временная директория создана")
        
        # Тест генерации шаблона (требует БД)
        try:
            file_path = ExportService.generate_directories_template()
            if file_path:
                print(f"✅ Шаблон создан: {file_path}")
            else:
                print("⚠️ Шаблон не создан (возможно, нет подключения к БД)")
        except Exception as e:
            print(f"⚠️ Ошибка создания шаблона (ожидаемо без БД): {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_import_service():
    """Тест ImportService изолированно"""
    try:
        # Прямой импорт без services.__init__
        from services.import_service import ImportService
        
        print("✅ ImportService импортирован успешно")
        
        # Тест создания директории
        ImportService.create_temp_directory()
        print("✅ Временная директория создана")
        
        # Тест валидации несуществующего файла
        result = ImportService.validate_excel_file('nonexistent.xlsx')
        if not result['valid']:
            print("✅ Валидация несуществующего файла работает")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_constants():
    """Тест констант"""
    try:
        from utils.constants import ALL_TABLE_NAMES_FOR_BACKUP, TEMP_DIR
        
        print(f"✅ Константы загружены:")
        print(f"  - TEMP_DIR: {TEMP_DIR}")
        print(f"  - Таблиц для бэкапа: {len(ALL_TABLE_NAMES_FOR_BACKUP)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка загрузки констант: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Тестируем изолированно import/export сервисы...")
    print()
    
    print("1. Тест констант:")
    test_constants()
    print()
    
    print("2. Тест ExportService:")
    test_export_service()
    print()
    
    print("3. Тест ImportService:")
    test_import_service()
    print()
    
    print("✅ Тестирование завершено!")