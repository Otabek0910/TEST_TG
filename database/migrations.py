import logging
from database.queries import db_execute, db_query

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

async def add_discipline_to_personnel_roles():
    """Добавляет поле discipline_id в таблицу personnel_roles"""
    try:
        # Проверяем есть ли уже поле discipline_id
        column_exists = await db_query("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'personnel_roles' AND column_name = 'discipline_id'
            )
        """)
        
        if not column_exists or not column_exists[0][0]:
            # Добавляем поле discipline_id
            await db_execute("""
                ALTER TABLE personnel_roles 
                ADD COLUMN discipline_id INTEGER REFERENCES disciplines(id)
            """)
            logger.info("✅ Добавлено поле discipline_id в personnel_roles")
        else:
            logger.info("✅ Поле discipline_id уже существует в personnel_roles")
            
    except Exception as e:
        logger.error(f"❌ Ошибка добавления discipline_id: {e}")

async def create_personnel_roles_by_disciplines():
    """Создает роли ТОЛЬКО ОДИН РАЗ - при первом запуске"""
    try:
        # Проверяем есть ли уже роли
        existing_roles_count = await db_query("SELECT COUNT(*) FROM personnel_roles")
        
        if existing_roles_count and existing_roles_count[0][0] > 0:
            logger.info(f"✅ Роли персонала уже существуют ({existing_roles_count[0][0]} шт.), пропускаем создание")
            return
        
        logger.info("🔄 Создаем роли персонала (первый запуск)...")
        
        # Получаем дисциплины или создаем базовые
        disciplines = await db_query("SELECT id, name FROM disciplines ORDER BY name")
        if not disciplines:
            logger.info("🔄 Создаем базовые дисциплины...")
            base_disciplines = [
                'Механомонтаж', 'Бетонные работы', 'КИПиА', 'Металлоконструкция',
                'Отделочные работы', 'Трубопровод', 'Земляные работы', 'Электромонтажные работы'
            ]
            for disc_name in base_disciplines:
                await db_execute(
                    "INSERT INTO disciplines (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                    (disc_name,)
                )
            disciplines = await db_query("SELECT id, name FROM disciplines ORDER BY name")
        
        # Роли по дисциплинам
        roles_by_discipline = {
            'Механомонтаж': [
                'Слесарь-монтажник 6 разряда',
                'Слесарь-монтажник 5 разряда', 
                'Слесарь-монтажник 4 разряда',
                'Помощник слесаря',
                'Крановщик',
                'Стропальщик',
                'Монтажник оборудования',
                'Мастер участка'
            ],
            'Бетонные работы': [
                'Бетонщик 6 разряда',
                'Бетонщик 5 разряда',
                'Бетонщик 4 разряда',
                'Арматурщик 6 разряда',
                'Арматурщик 5 разряда',
                'Помощник бетонщика',
                'Машинист бетононасоса',
                'Мастер участка'
            ],
            'КИПиА': [
                'Слесарь КИПиА 6 разряда',
                'Слесарь КИПиА 5 разряда',
                'Электромонтер КИПиА 6 разряда',
                'Электромонтер КИПиА 5 разряда',
                'Наладчик КИПиА',
                'Помощник монтажника',
                'Мастер участка'
            ],
            'Металлоконструкция': [
                'Сварщик 6 разряда',
                'Сварщик 5 разряда',
                'Сварщик 4 разряда',
                'Слесарь по сборке 6 разряда',
                'Слесарь по сборке 5 разряда',
                'Помощник сварщика',
                'Крановщик',
                'Стропальщик',
                'Мастер участка'
            ],
            'Отделочные работы': [
                'Маляр 6 разряда',
                'Маляр 5 разряда',
                'Штукатур 6 разряда',
                'Штукатур 5 разряда',
                'Плиточник 6 разряда',
                'Плиточник 5 разряда',
                'Помощник отделочника',
                'Мастер участка'
            ],
            'Трубопровод': [
                'Сварщик труб 6 разряда',
                'Сварщик труб 5 разряда',
                'Монтажник труб 6 разряда',
                'Монтажник труб 5 разряда',
                'Слесарь-трубопроводчик 6 разряда',
                'Слесарь-трубопроводчик 5 разряда',
                'Помощник монтажника',
                'Изолировщик',
                'Мастер участка'
            ],
            'Земляные работы': [
                'Машинист экскаватора 6 разряда',
                'Машинист экскаватора 5 разряда',
                'Машинист бульдозера 6 разряда',
                'Машинист бульдозера 5 разряда',
                'Тракторист',
                'Землекоп',
                'Стропальщик',
                'Мастер участка'
            ],
            'Электромонтажные работы': [
                'Электромонтажник 6 разряда',
                'Электромонтажник 5 разряда',
                'Электромонтажник 4 разряда',
                'Кабельщик-спайщик 6 разряда',
                'Кабельщик-спайщик 5 разряда',
                'Электрик 6 разряда',
                'Электрик 5 разряда',
                'Помощник электрика',
                'Мастер участка'
            ]
        }
        
        # Создаем роли для каждой дисциплины
        total_created = 0
        for disc_id, disc_name in disciplines:
            if disc_name in roles_by_discipline:
                for i, role_name in enumerate(roles_by_discipline[disc_name], 1):
                    await db_execute("""
                        INSERT INTO personnel_roles (role_name, discipline_id, display_order, category)
                        VALUES (%s, %s, %s, %s)
                    """, (role_name, disc_id, i, 'Основной персонал'))
                    total_created += 1
                    
                logger.info(f"✅ Создано {len(roles_by_discipline[disc_name])} ролей для {disc_name}")
        
        logger.info(f"✅ Всего создано {total_created} ролей персонала по дисциплинам")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания ролей по дисциплинам: {e}")

async def run_all_migrations():
    """Запускает все миграции - ДОПОЛНЕНО РОЛЯМИ ПО ДИСЦИПЛИНАМ"""
    logger.info("🔄 Запуск миграций БД...")
    
    if not await create_initial_tables():
        logger.critical("❌ Не удалось создать базовые таблицы")
        return False
    
    if not await create_indexes():
        logger.warning("⚠️ Не удалось создать индексы, но миграция продолжается")
    
    # ADDED: Добавляем поле discipline_id в personnel_roles
    await add_discipline_to_personnel_roles()
    
    # ADDED: Создаем роли по дисциплинам
    await create_personnel_roles_by_disciplines()
    
    logger.info("✅ Миграции успешно завершены!")
    return True