from database.queries import db_query, db_execute

# Переводы интерфейса
TRANSLATIONS = {
    'ru': {
        # Основное меню
        'main_menu_title': "🏠 Главное меню",
        'submit_roster_button': "📋 Подать табель на сегодня",
        'form_report_button': "📝 Сформировать отчет",
        'view_reports_button': "📊 Просмотр отчетов",
        'profile_button': "👤 Профиль",
        'auth_button': "🔐 Авторизация",
        'manage_button': "⚙️ Управление",
        'reports_group_button': "➡️ Перейти в группу отчетов",
        'change_language_button': "🌐 Язык",
        'back_button': "◀️ Назад",
        'forward_button': "▶️ Далее",
        'cancel_button': "❌ Отмена",
        'yes_button': "✅ Да",
        'no_button': "❌ Нет",
        'skip_button': "⏩ Пропустить",
        'welcome_message': "👋 Добро пожаловать в систему управления строительными отчетами!",
        
        # Авторизация
        'auth_prompt_role': "🔐 <b>Выберите вашу роль:</b>",
        'auth_role_manager': "Менеджер",
        'auth_role_foreman': "Бригадир", 
        'auth_role_pto': "ПТО",
        'auth_role_kiok': "КИОК",
        'auth_prompt_name': "📝 <b>Введите ваше имя и фамилию</b> (например: Иван Петров):",
        'auth_error_name': "❗ <b>Ошибка: введите имя и фамилию через пробел.</b>\n\n📝 <b>Попробуйте еще раз:</b>",
        'auth_prompt_contact': "📞 <b>Отлично! Теперь нажмите кнопку ниже, чтобы поделиться контактной информацией.</b>",
        'auth_contact_button': "📞 Поделиться контактом",
        'auth_pending_approval': "✅ <b>Данные получены.</b>\n\n<b>Ваш запрос отправлен на подтверждение. Ожидайте...</b>",
        'auth_role_approved_user': "🎉 Ваша роль «{role}» подтверждена!",
        'auth_prompt_manager_level': "⚙️ <b>Финальный шаг: выберите ваш уровень управления:</b>",
        'auth_manager_level1': "Уровень 1 (полный доступ)",
        'auth_manager_level2': "Уровень 2 (по дисциплине)",
        'auth_prompt_discipline': "⚙️ <b>Финальный шаг: выберите вашу дисциплину для роли «{role}»:</b>",
        # Отчеты
        'report_step1_discipline': "Выберите дисциплину:",
        'report_step2_work_type': "Выберите вид работ для «{discipline}»:",
        'page_of': "Страница {page} из {total_pages}",
        
        # Табели
        'roster_prompt': "📋 *Подача табеля на {date}*\n\nВведите количество человек через запятую в следующем порядке:\n{roles_list}",
        'roster_error_mismatch': "❌ Введено {input_count} чисел, а требуется {expected_count}. Попробуйте еще раз:",
        'roster_error_no_people': "❌ Общее количество людей должно быть больше 0. Попробуйте еще раз:",
        'roster_already_submitted': "✅ Табель на сегодня уже подан.",
        
        # Общие
        'loading_please_wait': "⏳ Загружается, пожалуйста подождите...",
        'error_generic': "❌ Произошла ошибка. Попробуйте еще раз.",
        'language_prompt': "🌐 Выберите язык / Choose language / Tilni tanlang:",
        'language_changed': "✅ Язык изменен.",
        'back_to_main_menu_button': "🏠 В главное меню",
        
        # Уведомления
        'master_report_reminder_notification': "⏰ <b>Напоминание о проверке отчета</b>\n\nОтчет ID:{report_id} ожидает вашего подтверждения более 2 дней.\n\n👤 Супервайзер: {supervisor}\n👥 Бригада: {brigade}\n🔧 Работы: {work_type}",


        'roster_submit_button': '📋 Подать табель',
        'roster_submitted_button': '✅ Табель подан',
        'roster_confirm_prompt': 'Подтверждение табеля:\n{summary}\nВсего: {total} чел.',
        'roster_error_invalid_format': '❌ Неверный формат. Попробуйте еще раз.',
        'roster_saved_safely': '✅ Табель сохранен. Резерв: {reserve} чел.',
        'roster_dangerous_save_warning': '⚠️ Новый табель: {new_total}, назначено: {assigned}',
        'roster_force_save_button': '⚠️ Сохранить принудительно',
        'roster_force_saved_success': '✅ Табель принудительно сохранен',
        
    },
    
    'en': {
        # Main menu
        'main_menu_title': "🏠 Main Menu",
        'submit_roster_button': "📋 Submit Today's Roster",
        'form_report_button': "📝 Create Report", 
        'view_reports_button': "📊 View Reports",
        'profile_button': "👤 Profile",
        'auth_button': "🔐 Authorization",
        'manage_button': "⚙️ Management",
        'reports_group_button': "➡️ Go to reports group",
        'change_language_button': "🌐 Language",
        'back_button': "◀️ Back",
        'forward_button': "▶️ Next",
        'cancel_button': "❌ Cancel",
        'yes_button': "✅ Yes",
        'no_button': "❌ No", 
        'skip_button': "⏩ Skip",
        'welcome_message': "👋 Welcome to the construction reports management system!",
        
        # Authorization
        'auth_prompt_role': "🔐 <b>Choose your role:</b>",
        'auth_role_manager': "Manager",
        'auth_role_foreman': "Foreman",
        'auth_role_pto': "PTO",
        'auth_role_kiok': "QCC",
        'auth_prompt_name': "📝 <b>Enter your first and last name</b> (e.g., John Smith):",
        'auth_error_name': "❗ <b>Error: enter first and last name separated by space.</b>\n\n📝 <b>Try again:</b>",
        'auth_prompt_contact': "📞 <b>Great! Now press the button below to share your contact information.</b>",
        'auth_contact_button': "📞 Share contact",
        'auth_pending_approval': "✅ <b>Data received.</b>\n\n<b>Your request has been sent for approval. Please wait...</b>",
        'auth_role_approved_user': "🎉 Your role «{role}» has been approved!",
        'auth_prompt_manager_level': "⚙️ <b>Final step: select your management level:</b>",
        'auth_manager_level1': "Level 1 (full access)",
        'auth_manager_level2': "Level 2 (by discipline)",
        'auth_prompt_discipline': "⚙️ <b>Final step: select your discipline for the «{role}» role:</b>",
        # Reports
        'report_step1_discipline': "Select discipline:",
        'report_step2_work_type': "Select work type for «{discipline}»:",
        'page_of': "Page {page} of {total_pages}",
        
        # Rosters
        'roster_prompt': "📋 *Roster submission for {date}*\n\nEnter number of people separated by comma in this order:\n{roles_list}",
        'roster_error_mismatch': "❌ Entered {input_count} numbers, but {expected_count} required. Try again:",
        'roster_error_no_people': "❌ Total number of people must be greater than 0. Try again:",
        'roster_already_submitted': "✅ Today's roster already submitted.",
        
        # Common
        'loading_please_wait': "⏳ Loading, please wait...",
        'error_generic': "❌ An error occurred. Please try again.",
        'language_prompt': "🌐 Выберите язык / Choose language / Tilni tanlang:",
        'language_changed': "✅ Language changed.",
        'back_to_main_menu_button': "🏠 To main menu",
 
        # Notifications (EN)
        'master_report_reminder_notification_en': "⏰ <b>Report Approval Reminder</b>\n\nReport ID:{report_id} has been waiting for your approval for more than 2 days.\n\n👤 Supervisor: {supervisor}\n👥 Brigade: {brigade}\n🔧 Work type: {work_type}",

        'roster_submit_button': '📋 Submit Roster',
        'roster_submitted_button': '✅ Roster Submitted',
        'roster_confirm_prompt': 'Roster Confirmation:\n{summary}\nTotal: {total} ppl.',
        'roster_error_invalid_format': '❌ Invalid format. Please try again.',
        'roster_saved_safely': '✅ Roster saved. Reserve: {reserve} ppl.',
        'roster_dangerous_save_warning': '⚠️ New roster: {new_total}, assigned: {assigned}',
        'roster_force_save_button': '⚠️ Force Save',
        'roster_force_saved_success': '✅ Roster force-saved',
        
    },
    
    'uz': {
        # Asosiy menyu
        'main_menu_title': "🏠 Asosiy menyu",
        'submit_roster_button': "📋 Bugungi tabelni topshirish",
        'form_report_button': "📝 Hisobot yaratish",
        'view_reports_button': "📊 Hisobotlarni ko'rish", 
        'profile_button': "👤 Profil",
        'auth_button': "🔐 Avtorizatsiya",
        'manage_button': "⚙️ Boshqaruv",
        'reports_group_button': "➡️ Hisobotlar guruhiga o'tish",
        'change_language_button': "🌐 Til",
        'back_button': "◀️ Orqaga",
        'forward_button': "▶️ Oldinga",
        'cancel_button': "❌ Bekor qilish",
        'yes_button': "✅ Ha",
        'no_button': "❌ Yo'q",
        'skip_button': "⏩ O'tkazib yuborish",
        'welcome_message': "👋 Qurilish hisobotlari boshqaruv tizimiga xush kelibsiz!",
        
        # Avtorizatsiya
        'auth_prompt_role': "🔐 <b>Rolingizni tanlang:</b>",
        'auth_role_manager': "Menejer",
        'auth_role_foreman': "Brigadir",
        'auth_role_pto': "PTO",
        'auth_role_kiok': "KIOK",
        'auth_prompt_name': "📝 <b>Ism va familiyangizni kiriting</b> (masalan: Ahmadjon Karimov):",
        'auth_error_name': "❗ <b>Xato: ism va familiyani bo'sh joy bilan ajratib kiriting.</b>\n\n📝 <b>Qayta urinib ko'ring:</b>",
        'auth_prompt_contact': "📞 <b>Ajoyib! Endi kontakt ma'lumotlarini ulashish uchun quyidagi tugmani bosing.</b>",
        'auth_contact_button': "📞 Kontaktni ulashish",
        'auth_pending_approval': "✅ <b>Ma'lumotlar qabul qilindi.</b>\n\n<b>So'rovingiz tasdiqlash uchun yuborildi. Kuting...</b>",
        'auth_role_approved_user': "🎉 Sizning «{role}» rolingiz tasdiqlandi!",
        'auth_prompt_manager_level': "⚙️ <b>So'nggi qadam: boshqaruv darajangizni tanlang:</b>",
        'auth_manager_level1': "1-daraja (to'liq kirish)",
        'auth_manager_level2': "2-daraja (yo'nalish bo'yicha)",
        'auth_prompt_discipline': "⚙️ <b>So'nggi qadam: «{role}» roli uchun yo'nalishingizni tanlang:</b>",
        # Hisobotlar
        'report_step1_discipline': "Yo'nalishni tanlang:",
        'report_step2_work_type': "«{discipline}» uchun ish turini tanlang:",
        'page_of': "{total_pages} dan {page}-sahifa",
        
        # Tabellar
        'roster_prompt': "📋 *{date} uchun tabel topshirish*\n\nQuyidagi tartibda vergul bilan ajratib odamlar sonini kiriting:\n{roles_list}",
        'roster_error_mismatch': "❌ {input_count} ta raqam kiritildi, lekin {expected_count} ta kerak. Qayta urinib ko'ring:",
        'roster_error_no_people': "❌ Jami odamlar soni 0 dan katta bo'lishi kerak. Qayta urinib ko'ring:",
        'roster_already_submitted': "✅ Bugungi tabel allaqachon topshirilgan.",
        
        # Umumiy
        'loading_please_wait': "⏳ Yuklanmoqda, iltimos kuting...",
        'error_generic': "❌ Xatolik yuz berdi. Qayta urinib ko'ring.",
        'language_prompt': "🌐 Выберите язык / Choose language / Tilni tanlang:",
        'language_changed': "✅ Til o'zgartirildi.",
        'back_to_main_menu_button': "🏠 Asosiy menyuga",

        # Notifications (UZ)
        'master_report_reminder_notification_uz': "⏰ <b>Hisobotni tasdiqlash eslatmasi</b>\n\nID:{report_id} hisobot 2 kundan ortiq tasdiqlashingizni kutmoqda.\n\n👤 Supervayzer: {supervisor}\n👥 Brigada: {brigade}\n🔧 Ish turi: {work_type}",
    
        'roster_submit_button': '📋 Tabelni yuborish',
        'roster_submitted_button': '✅ Tabel yuborildi',
        'roster_confirm_prompt': 'Tabelni tasdiqlash:\n{summary}\nJami: {total} kishi.',
        'roster_error_invalid_format': '❌ Noto‘g‘ri format. Qayta urinib ko‘ring.',
        'roster_saved_safely': '✅ Tabel saqlandi. Zaxira: {reserve} kishi.',
        'roster_dangerous_save_warning': '⚠️ Yangi tabel: {new_total}, biriktirilgan: {assigned}',
        'roster_force_save_button': '⚠️ Majburan saqlash',
        'roster_force_saved_success': '✅ Tabel majburan saqlandi',
    
    
    
    
    }
}

# Переводы данных из БД
DATA_TRANSLATIONS = {
    # Дисциплины
    'Механомонтаж': {'en': 'Mechanical Installation', 'uz': 'Mexanik montaj'},
    'Бетонные работы': {'en': 'Concrete Works', 'uz': 'Beton ishlari'},
    'КИПиА': {'en': 'Instrumentation & Automation', 'uz': 'O\'lchov asboblari va avtomatika'},
    'Металлоконструкция': {'en': 'Steel Structures', 'uz': 'Metall konstruksiyalar'},
    'Отделочные работы': {'en': 'Finishing Works', 'uz': 'Pardozlash ishlari'},
    'Трубопровод': {'en': 'Piping', 'uz': 'Quvurlar'},
    'Земляные работы': {'en': 'Earthworks', 'uz': 'Yer ishlari'},
    
    # Единицы измерения
    'ТН': {'en': 't', 'uz': 't'},
    'М3': {'en': 'm³', 'uz': 'm³'},
    'М2': {'en': 'm²', 'uz': 'm²'},
    'М': {'en': 'm', 'uz': 'm'},
    'ШТ': {'en': 'pcs', 'uz': 'dona'},
    'чел.час': {'en': 'man-hour', 'uz': 'odam-soat'},
    'компл': {'en': 'set', 'uz': 'kompl'},
    'п.м': {'en': 'lm', 'uz': 'p.m'},
    'кг': {'en': 'kg', 'uz': 'kg'},

    # Workflow и уведомления
        'master_no_pending_reports': "📭 Нет отчетов для подтверждения",
        'master_pending_reports_title': "📋 Отчеты для подтверждения ({count})",
        'master_approval_success': "✅ Отчет ID:{report_id} успешно подтвержден",
        'master_approval_error': "❌ Ошибка при подтверждении отчета",
        'master_rejection_reason_prompt': "📝 Укажите причину отклонения отчета:",
        'master_rejection_success': "❌ Отчет ID:{report_id} отклонен",
        'master_rejection_error': "❌ Ошибка при отклонении отчета",
        
        'kiok_no_pending_reports': "📭 Нет отчетов для проверки",
        'kiok_pending_reports_title': "🔍 Отчеты для проверки ({count})",
        'kiok_inspection_number_prompt': "📝 Введите номер проверки:",
        'kiok_approval_success': "✅ Отчет ID:{report_id} согласован (№{inspection_number})",
        'kiok_approval_error': "❌ Ошибка при согласовании отчета",
        'kiok_rejection_reason_prompt': "📝 Укажите причину отклонения и замечания:",
        'kiok_rejection_success': "❌ Отчет ID:{report_id} отклонен с замечаниями",
        'kiok_rejection_error': "❌ Ошибка при отклонении отчета",
        
        # Уведомления
        'roster_morning_reminder': "🌅 Доброе утро, {name}!\n\n📋 Напоминаем подать табель на {date}",
        'remind_later_button': "⏰ Напомнить позже",
        'master_new_report_notification': "🔔 Новый отчет для подтверждения\n\n👤 Супервайзер: {supervisor}\n👥 Бригада: {brigade}\n🏗️ Корпус: {corpus}\n🔧 Работы: {work_type}\n📅 Дата: {date}\n\n📋 ID отчета: {report_id}",
        'kiok_new_report_notification': "🔔 Новый отчет для проверки\n\n👥 Бригада: {brigade}\n🏗️ Корпус: {corpus}\n🔧 Работы: {work_type}\n📅 Дата: {date}\n✅ Подтвердил: {master}\n\n📋 ID отчета: {report_id}",
        'supervisor_report_approved': "🎉 Ваш отчет ID:{report_id} УТВЕРЖДЕН!\n\n👥 Бригада: {brigade}\n🔧 Работы: {work_type}\n📅 Дата: {date}",
        'supervisor_report_rejected': "❌ Ваш отчет ID:{report_id} ОТКЛОНЕН\n\n👥 Бригада: {brigade}\n🔧 Работы: {work_type}\n📅 Дата: {date}\n\n💬 Причина: {reason}",
        'supervisor_report_status_changed': "📝 Изменен статус отчета ID:{report_id}\n\n👥 Бригада: {brigade}\n🔧 Работы: {work_type}\n📅 Дата: {date}",
        
        # Кнопки
        'approve_button': "✅ Подтвердить",
        'reject_button': "❌ Отклонить", 
        'view_details_button': "👁️ Подробнее",
        'kiok_approve_button': "✅ Согласовать",
        'kiok_reject_button': "❌ Отклонить",
        'create_new_report_button': "📝 Создать новый отчет",
        'view_my_reports_button': "📊 Мои отчеты",
        
}

DEFAULT_LANGUAGE = 'ru'

def get_text(key: str, lang_code: str = DEFAULT_LANGUAGE) -> str:
    """Возвращает переведенную строку по ключу и коду языка."""
    if not lang_code:
        lang_code = DEFAULT_LANGUAGE
    return TRANSLATIONS.get(lang_code, TRANSLATIONS[DEFAULT_LANGUAGE]).get(key, f"_{key}_")

def get_data_translation(original_text: str, lang_code: str = 'ru') -> str:
    """Переводит данные из БД (названия дисциплин, работ и т.д.)."""
    if lang_code == 'ru' or not original_text:
        return original_text
    
    cleaned_text = original_text.strip()
    return DATA_TRANSLATIONS.get(cleaned_text, {}).get(lang_code, cleaned_text)

async def get_user_language(user_id: str) -> str: # FIXED: async def
    """Асинхронно получает язык пользователя из любой таблицы ролей."""
    tables = ['admins', 'managers', 'supervisors', 'masters', 'brigades', 'pto', 'kiok']
    for table in tables:
        # FIXED: await
        lang_code_raw = await db_query(f"SELECT language_code FROM {table} WHERE user_id = %s", (user_id,))
        if lang_code_raw and lang_code_raw[0] and lang_code_raw[0][0]:
            return lang_code_raw[0][0]
    return 'ru'

async def update_user_language(user_id: str, lang_code: str): # FIXED: async def
    """Асинхронно обновляет язык пользователя во всех таблицах."""
    tables = ['admins', 'managers', 'supervisors', 'masters', 'brigades', 'pto', 'kiok']
    for table in tables:
        # FIXED: await
        await db_execute(f"UPDATE {table} SET language_code = %s WHERE user_id = %s", (lang_code, user_id))