import logging
from database.queries import db_execute

logger = logging.getLogger(__name__)

async def create_initial_tables():
    """Создает все необходимые таблицы с унифицированной схемой."""
    
    tables_sql = [
        # ... (все ваши таблицы до 'reports' остаются без изменений) ...
        
        # Дисциплины
        """
        CREATE TABLE IF NOT EXISTS disciplines (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Объекты строительства
        """
        CREATE TABLE IF NOT EXISTS construction_objects (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Типы работ
        """
        CREATE TABLE IF NOT EXISTS work_types (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            discipline_id INTEGER NOT NULL REFERENCES disciplines(id),
            unit_of_measure TEXT,
            norm_per_unit REAL,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Админы
        """
        CREATE TABLE IF NOT EXISTS admins (
            user_id VARCHAR(255) PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            phone_number TEXT,
            language_code VARCHAR(2) DEFAULT 'ru',
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Менеджеры
        """
        CREATE TABLE IF NOT EXISTS managers (
            user_id VARCHAR(255) PRIMARY KEY,
            level INTEGER NOT NULL,
            discipline INTEGER REFERENCES disciplines(id),
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            phone_number TEXT,
            language_code VARCHAR(2) DEFAULT 'ru',
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Бригады
        """
        CREATE TABLE IF NOT EXISTS brigades (
            user_id VARCHAR(255) PRIMARY KEY,
            brigade_name TEXT NOT NULL,
            discipline_id INTEGER REFERENCES disciplines(id),
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            phone_number TEXT,
            language_code VARCHAR(2) DEFAULT 'ru',
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # ПТО
        """
        CREATE TABLE IF NOT EXISTS pto (
            user_id VARCHAR(255) PRIMARY KEY,
            discipline_id INTEGER REFERENCES disciplines(id),
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            phone_number TEXT,
            language_code VARCHAR(2) DEFAULT 'ru',
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Супервайзеры
        """
        CREATE TABLE IF NOT EXISTS supervisors (
            user_id VARCHAR(255) PRIMARY KEY,
            supervisor_name TEXT NOT NULL,
            discipline_id INTEGER REFERENCES disciplines(id),
            brigade_ids TEXT[],
            phone_number TEXT,
            language_code VARCHAR(2) DEFAULT 'ru',
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Мастера
        """
        CREATE TABLE IF NOT EXISTS masters (
            user_id VARCHAR(255) PRIMARY KEY,
            master_name TEXT NOT NULL,
            discipline_id INTEGER REFERENCES disciplines(id),
            can_approve_reports BOOLEAN DEFAULT true,
            signature_template TEXT,
            phone_number TEXT,
            language_code VARCHAR(2) DEFAULT 'ru',
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # КИОК
        """
        CREATE TABLE IF NOT EXISTS kiok (
            user_id VARCHAR(255) PRIMARY KEY,
            kiok_name TEXT NOT NULL,
            discipline_id INTEGER REFERENCES disciplines(id),
            inspection_permissions TEXT[],
            phone_number TEXT,
            language_code VARCHAR(2) DEFAULT 'ru',
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Отчеты (FIXED)
        """
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            supervisor_id VARCHAR(255) REFERENCES supervisors(user_id),
            report_date DATE NOT NULL,
            brigade_name TEXT NOT NULL,
            corpus_name TEXT NOT NULL,
            discipline_id INTEGER REFERENCES disciplines(id),
            work_type_name TEXT NOT NULL,
            workflow_status VARCHAR(50) DEFAULT 'pending_master',
            supervisor_signed_at TIMESTAMP,
            master_id VARCHAR(255) REFERENCES masters(user_id),
            master_signed_at TIMESTAMP,
            master_signature_path TEXT,
            kiok_id VARCHAR(255) REFERENCES kiok(user_id),
            kiok_signed_at TIMESTAMP,
            kiok_inspection_number TEXT,
            kiok_attachments JSONB DEFAULT '[]',
            kiok_remark_document TEXT,
            kiok_notes TEXT,
            report_data JSONB DEFAULT '{}'
        )
        """,
        
        # Справочник бригад
        """
        CREATE TABLE IF NOT EXISTS brigades_reference (
            id SERIAL PRIMARY KEY,
            brigade_name TEXT NOT NULL UNIQUE,
            discipline_id INTEGER REFERENCES disciplines(id),
            supervisor_id VARCHAR(255) REFERENCES supervisors(user_id),
            brigade_size INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Topic mappings
        """
        CREATE TABLE IF NOT EXISTS topic_mappings (
            id SERIAL PRIMARY KEY,
            telegram_topic_id INTEGER,
            discipline_id INTEGER REFERENCES disciplines(id),
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Personnel roles
        """
        CREATE TABLE IF NOT EXISTS personnel_roles (
            id SERIAL PRIMARY KEY,
            role_name TEXT NOT NULL UNIQUE,
            category TEXT,
            display_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
        
        # Daily rosters
        """
        CREATE TABLE IF NOT EXISTS daily_rosters (
            id SERIAL PRIMARY KEY,
            brigade_user_id VARCHAR(255) NOT NULL,
            roster_date DATE NOT NULL,
            total_personnel INTEGER DEFAULT 0,
            is_submitted BOOLEAN DEFAULT false,
            submitted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(brigade_user_id, roster_date)
        )
        """,
        
        # Daily roster details
        """
        CREATE TABLE IF NOT EXISTS daily_roster_details (
            id SERIAL PRIMARY KEY,
            roster_id INTEGER REFERENCES daily_rosters(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES personnel_roles(id),
            personnel_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(roster_id, role_id)
        )
        """,

        """
        CREATE TABLE IF NOT EXISTS scheduled_notifications (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(20) NOT NULL,
            notification_type VARCHAR(50) NOT NULL,
            scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
            message_text TEXT NOT NULL,
            is_sent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    
    try:
        for sql in tables_sql:
            await db_execute(sql)
        
        logger.info("✅ Все таблицы созданы успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при создании таблиц: {e}")
        return False

async def create_indexes():
    """Создает индексы для оптимизации производительности с исправленными именами столбцов."""
    try:
        # # FIXED: Упрощенная и надежная логика создания индексов.
        # Все проверки на существование делает сам SQL с помощью "IF NOT EXISTS".
        all_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_reports_supervisor ON reports(supervisor_id)",
            "CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(report_date)",
            "CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(workflow_status)",
            # # FIXED: Индекс для discipline_id
            "CREATE INDEX IF NOT EXISTS idx_reports_discipline ON reports(discipline_id)",
            "CREATE INDEX IF NOT EXISTS idx_daily_rosters_date ON daily_rosters(roster_date)",
            "CREATE INDEX IF NOT EXISTS idx_daily_rosters_brigade ON daily_rosters(brigade_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_work_types_discipline ON work_types(discipline_id)",
            "CREATE INDEX IF NOT EXISTS idx_reports_master ON reports(master_id)",
            "CREATE INDEX IF NOT EXISTS idx_reports_kiok ON reports(kiok_id)",
            # # FIXED: Индексы для discipline_id в таблицах ролей
            "CREATE INDEX IF NOT EXISTS idx_supervisors_discipline ON supervisors(discipline_id)",
            "CREATE INDEX IF NOT EXISTS idx_masters_discipline ON masters(discipline_id)",
            "CREATE INDEX IF NOT EXISTS idx_kiok_discipline ON kiok(discipline_id)",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_user_id ON scheduled_notifications(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_scheduled_time ON scheduled_notifications(scheduled_time)",
            "CREATE INDEX IF NOT EXISTS idx_scheduled_notifications_is_sent ON scheduled_notifications(is_sent)"
        ]    
        for index_sql in all_indexes:
            await db_execute(index_sql)
            
        logger.info("✅ Индексы созданы успешно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания индексов: {e}")
        return False
        

async def run_all_migrations():
    """Запускает все миграции."""
    logger.info("🔄 Запуск миграций БД...")
    
    if not await create_initial_tables():
        logger.critical("❌ Не удалось создать базовые таблицы")
        return False
    
    if not await create_indexes():
        logger.warning("⚠️ Не удалось создать индексы, но миграция продолжается")
    
    logger.info("✅ Миграции успешно завершены!")
    return True