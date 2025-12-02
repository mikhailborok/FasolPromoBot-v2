# Упрощенный импорт - сначала базовые импорты
import sqlite3
from datetime import datetime, timedelta
import logging
import os
import json
from io import BytesIO
import re
import random  
import asyncio  

# Импорт из telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Импорт config
from config import BOT_TOKEN

# Импорт из database - ОДНОЙ СТРОКОЙ
from database import *

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния пользователя
USER_STATES = {}
ADMIN_SESSIONS = {}
# Для хранения выбранного магазина мастер-админом
MASTER_ADMIN_SELECTED_STORE = {}
# Для отслеживания, что мастер смотрит статистику
MASTER_VIEWING_STATS = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начальная команда"""
    user_id = update.effective_user.id
    
    # Получаем store_id пользователя
    # get_user возвращает store_id (int) или None
    store_id = get_user(user_id) 
    
    # Проверяем, есть ли у пользователя выбранный магазин
    # Если store_id не None и не 0 (на случай, если в БД может быть 0), 
    # считаем, что магазин выбран
    if store_id is not None and store_id != 0: 
        # Меню для пользователя с выбранным магазином
        keyboard = [
            [KeyboardButton("🏪 Мой магазин"), KeyboardButton("🎁 Получить акцию")],
            [KeyboardButton("📱 Мои купоны"), KeyboardButton("🔄 Сменить магазин")],
            [KeyboardButton("💳 Погасить купон (для продавцов)"), KeyboardButton("👨‍💼 Вход для администратора")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # --- Отправка изображения с подписью ---
        photo_path = "Fasol.png"
        
        # Проверяем, существует ли файл
        if os.path.exists(photo_path):
            try:
                with open(photo_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption="🛒 Добро пожаловать в бота для магазинов Фасоль!\n"
                                "Здесь вы можете получать акции и скидки 🎉\n"
                                "Выберите действие из меню:",
                        reply_markup=reply_markup
                    )
                return # Успешно отправили фото, выходим
            except Exception as e:
                logger.error(f"Ошибка при отправке фото: {e}")
                # Если ошибка отправки фото, отправляем обычный текст
                await update.message.reply_text(
                    "🛒 Добро пожаловать в бота для магазинов Фасоль!\n"
                    "Здесь вы можете получать акции и скидки 🎉\n"
                    "Выберите действие из меню:",
                    reply_markup=reply_markup
                )
        else:
            logger.warning(f"Файл изображения не найден: {photo_path}")
            # Если файл не найден, отправляем обычный текст
            await update.message.reply_text(
                "🛒 Добро пожаловать в бота для магазинов Фасоль!\n"
                "Здесь вы можете получать акции и скидки 🎉\n"
                "Выберите действие из меню:",
                reply_markup=reply_markup
            )
    else:
        # Меню для нового пользователя или без выбранного магазина (только 2 кнопки)
        # Убираем "Погасить купон" из этого меню, как требовалось
        keyboard = [
            [KeyboardButton("🏪 Выбрать магазин"), KeyboardButton("👨‍💼 Вход для администратора")]
            # [KeyboardButton("💳 Погасить купон")] # Убираем эту кнопку
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # --- Отправка изображения с подписью для нового пользователя ---
        photo_path = "Fasol.png"
        
        # Проверяем, существует ли файл
        if os.path.exists(photo_path):
            try:
                with open(photo_path, 'rb') as photo:
                    await update.message.reply_photo(
                        photo=photo,
                        caption="🛒 Добро пожаловать в бота для магазинов Фасоль!\n"
                                "Здесь вы можете получать акции и скидки 🎉\n"
                                "Для начала выберите магазин или войдите как администратор:",
                        reply_markup=reply_markup
                    )
                return # Успешно отправили фото, выходим
            except Exception as e:
                logger.error(f"Ошибка при отправке фото новому пользователю: {e}")
                # Если ошибка отправки фото, отправляем обычный текст
                await update.message.reply_text(
                    "🛒 Добро пожаловать в бота для магазинов Фасоль!\n"
                    "Здесь вы можете получать акции и скидки 🎉\n"
                    "Для начала выберите магазин или войдите как администратор:",
                    reply_markup=reply_markup
                )
        else:
            logger.warning(f"Файл изображения не найден для нового пользователя: {photo_path}")
            # Если файл не найден, отправляем обычный текст
            await update.message.reply_text(
                "🛒 Добро пожаловать в бота для магазинов Фасоль!\n"
                "Здесь вы можете получать акции и скидки 🎉\n"
                "Для начала выберите магазин или войдите как администратор:",
                reply_markup=reply_markup
            )

async def choose_store(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор магазина для пользователя"""
    cities = {}
    stores = get_stores()
    for store in stores:
        city = store['city']
        if city not in cities:
            cities[city] = []
        cities[city].append(store)

    keyboard = []
    for city in cities.keys():
        keyboard.append([InlineKeyboardButton(f"🏙 {city}", callback_data=f"user_city_{city}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🏙 Выберите ваш город:",
        reply_markup=reply_markup
    )

async def choose_admin_store(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор магазина для мастер-админа"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return

    # Правильная группировка магазинов по городам без дублирования
    cities = {}
    stores = get_stores()
    for store in stores:
        city = store['city']
        if city not in cities:
            cities[city] = []
        cities[city].append(store)

    # --- Формирование Inline клавиатуры для выбора города ---
    inline_keyboard = []
    for city in cities.keys():
        inline_keyboard.append([InlineKeyboardButton(f"🏙 {city}", callback_data=f"admin_city_{city}")])
    
    inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)
    
    # --- Формирование Reply клавиатуры с кнопкой "Назад" ---
    reply_keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

    # Отправляем сообщение с inline-клавиатурой для выбора города
    # и reply-клавиатурой с кнопкой "Назад"
    await update.message.reply_text(
        "🏙 Выберите город магазина:",
        reply_markup=inline_reply_markup # Inline клавиатура для городов
    )
    # Отправляем отдельное сообщение с reply-клавиатурой для "Назад"
    await update.message.reply_text(
        "↩️ Нажмите кнопку ниже, чтобы вернуться назад:",
        reply_markup=reply_reply_markup # Reply клавиатура для "Назад"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("user_city_"):
        city = data.replace("user_city_", "")
        stores = get_stores()
        city_stores = [store for store in stores if store['city'] == city]
        keyboard = []
        for store in city_stores:
            keyboard.append([InlineKeyboardButton(
                f"📍 {store['address']}", 
                callback_data=f"user_store_{store['id']}"
            )])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🏪 Выберите магазин в городе {city}:",
            reply_markup=reply_markup
        )
    elif data.startswith("user_store_"):
        store_id = int(data.replace("user_store_", ""))
        user = get_user(user_id)
        if user:
            conn = sqlite3.connect('fasoley_bot.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET store_id = ? WHERE telegram_id = ?", (store_id, user_id))
            conn.commit()
            conn.close()
        else:
            create_user(user_id, store_id)
        store = get_store(store_id)
        keyboard = [
            [KeyboardButton("🏪 Мой магазин"), KeyboardButton("🎁 Получить акцию")],
            [KeyboardButton("📱 Мои купоны"), KeyboardButton("🔄 Сменить магазин")],
            [KeyboardButton("💳 Погасить купон (для продавцов)"), KeyboardButton("👨‍💼 Вход для администратора")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await query.edit_message_text(
            f"✅ Отлично! Ваш магазин Фасоль:\n"
            f"📍 {store['address']}, {store['city']}\n\n"
            f"Теперь вы можете получать акции в этом магазине! 🎉"
        )
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text="Выберите действие:",
            reply_markup=reply_markup
        )
    # Обработка выбора города мастер-админом
    elif data.startswith("admin_city_"):
        city = data.replace("admin_city_", "")
        stores = get_stores()
        city_stores = [store for store in stores if store['city'] == city]
        keyboard = []
        for store in city_stores:
            keyboard.append([InlineKeyboardButton(
                f"📍 {store['address']}",
                callback_data=f"admin_store_{store['id']}"
            )])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🏪 Выберите магазин в городе {city}:",
            reply_markup=reply_markup
        )
    elif data.startswith("admin_store_"):
        store_id = int(data.replace("admin_store_", ""))
        user_id = query.from_user.id
        MASTER_ADMIN_SELECTED_STORE[user_id] = store_id
        await show_selected_store_menu(update, context, store_id)
    elif data == "cancel_redeem":
        await query.edit_message_text("❌ Погашение купона отменено")
        await start(query, context)

async def show_selected_store_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, store_id: int):
    """Показать меню действий над выбранным магазином для мастер-админа"""
    user_id = update.effective_user.id if isinstance(update, Update) else update.from_user.id
    # Проверка прав доступа
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        text = "❌ Доступ запрещен."
        if isinstance(update, Update) and update.callback_query:
             await update.callback_query.edit_message_text(text)
        else:
             await update.message.reply_text(text)
        return

    store = get_store(store_id)
    if not store:
        text = "❌ Магазин не найден."
        if isinstance(update, Update) and update.callback_query:
             await update.callback_query.edit_message_text(text)
        else:
             await update.message.reply_text(text)
        return

    keyboard = [
        [KeyboardButton("📊 Статистика магазина"), KeyboardButton("🎁 Управление акциями магазина")],
        [KeyboardButton("➕ Добавить акцию в магазин"), KeyboardButton("❌ Удалить акцию из магазина")],
        [KeyboardButton("🔙 Назад к выбору магазина")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    menu_text = f"🔧 УПРАВЛЕНИЕ МАГАЗИНОМ\n\n🏪 {store['name']}\n📍 {store['address']}, {store['city']}"
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(menu_text)
        await context.bot.send_message(chat_id=user_id, text="Выберите действие:", reply_markup=reply_markup)
    else: # Предполагаем, что это вызов из handle_message
        await update.message.reply_text(menu_text, reply_markup=reply_markup)

async def my_coupons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать мои купоны"""
    user_id = update.effective_user.id
    store_id = get_user(user_id)
    if not store_id:
        await update.message.reply_text("❌ Сначала выберите магазин!")
        return

    conn = sqlite3.connect('fasoley_bot.db')
    cursor = conn.cursor()
    
    # Сначала находим правильный user_id (id из таблицы users)
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    user_row = cursor.fetchone()
    
    if not user_row:
        conn.close()
        await update.message.reply_text("❌ Ошибка: пользователь не найден")
        return
        
    correct_user_id = user_row[0]
    
    # Теперь используем правильный user_id для поиска купонов
    cursor.execute("""
        SELECT uc.coupon_code, p.description, s.name, s.address, uc.created_at, p.valid_days, p.starts_today
        FROM user_coupons uc
        JOIN promotions p ON uc.promotion_id = p.id
        JOIN stores s ON p.store_id = s.id
        WHERE uc.user_id = ? AND uc.redeemed = 0
        ORDER BY uc.created_at DESC
    """, (correct_user_id,))
    
    active_coupons = cursor.fetchall()
    conn.close()

    if not active_coupons:
        await update.message.reply_text("📱 У вас нет активных купонов")
        return

    for coupon in active_coupons:
        coupon_code = coupon[0]
        description = coupon[1]
        store_name = coupon[2]
        store_address = coupon[3]
        created_at = datetime.strptime(coupon[4], '%Y-%m-%d %H:%M:%S').date()
        valid_days = coupon[5]
        starts_today = coupon[6]
        valid_until = created_at + timedelta(days=valid_days)
        
        # НОВОЕ: Определяем статус доступности акции
        today = datetime.now().date()
        if starts_today:
            # Если акция стартует день в день - всегда активна
            availability_status = "✅ Акция активна"
        else:
            # Если акция стартует на следующий день
            if today > created_at:
                # Прошел как минимум один день - акция активна
                availability_status = "✅ Акция активна"
            else:
                # Сегодня получили акцию, но она стартует завтра
                availability_status = "⏳ Акцией можно воспользоваться с завтрашнего дня!"

        await update.message.reply_text(
            f"🎁 {description}\n"
            f"🏪 \"Фасоль\", {store_address}\n"
            f"🔢 Код: <b>{coupon_code}</b>\n"
            f"📅 Дата получения: {created_at.strftime('%d.%m.%Y')}\n"
            f"⏳ Купон можно погасить до: {valid_until.strftime('%d.%m.%Y')}\n"
            f"📊 Статус: {availability_status}",
            parse_mode="HTML"
        )

async def my_store(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать информацию о моем магазине"""
    user_id = update.effective_user.id
    store_id = get_user(user_id)
    if not store_id:
        await update.message.reply_text("❌ Сначала выберите магазин!")
        await choose_store(update, context)
        return

    store = get_store(store_id)
    await update.message.reply_text(
        f"🏪 Ваш магазин \"Фасоль\":\n\n"
        f"🏙 {store['city']}\n"
        f"📍 {store['address']}\n\n"

        f"Здесь вы можете получать акции каждый день! 🎉"
    )

async def redeem_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запуск погашения купона по коду"""
    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "💳 ПОГАШЕНИЕ КУПОНА\n\n"
        "🔢 Введите 6-значный код купона:",
        reply_markup=reply_markup
    )
    USER_STATES[update.effective_user.id] = "redeeming_coupon"

async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вход для администратора"""
    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👨‍💼 Введите логин и пароль через пробел:\n"
        "Например: admin password",
        reply_markup=reply_markup
    )
    USER_STATES[update.effective_user.id] = "waiting_admin_credentials"

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, admin):
    """Показать админ-панель"""
    user_id = update.effective_user.id
    ADMIN_SESSIONS[user_id] = admin
    role = admin[3]
    store_id = admin[4] if len(admin) > 4 else None

    if role == "master":
        keyboard = [
            [KeyboardButton("📊 Общая статистика"), KeyboardButton("🎁 Управление акциями")],
            [KeyboardButton("🏪 Управление магазинами"), KeyboardButton("🔙 Выйти из админки")]
        ]
        welcome_text = f"🔧 МАСТЕР-ПАНЕЛЬ\n\nДобро пожаловать, {admin[1]}!"
    else:
        store = get_store(store_id) if store_id else None
        keyboard = [
            [KeyboardButton("📊 Статистика магазина"), KeyboardButton("🎁 Мои акции")],
            [KeyboardButton("➕ Добавить акцию"), KeyboardButton("❌ Удалить акцию")],
            [KeyboardButton("🔙 Выйти из админки")]
        ]
        store_name = store['name'] if store else "Неизвестный магазин"
        welcome_text = f"👨‍💼 АДМИН-ПАНЕЛЬ\n\nДобро пожаловать, {admin[1]}!\nМагазин: {store_name}"

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    # Если update - это callback_query, редактируем сообщение, иначе отправляем новое
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def show_store_stats_for_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика конкретного магазина"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS:
        await update.message.reply_text("❌ Сначала войдите в админ-панель")
        return

    admin = ADMIN_SESSIONS[user_id]
    role = admin[3]

    if role == "master":
        # Для мастер-админа проверяем, выбран ли магазин
        if user_id not in MASTER_ADMIN_SELECTED_STORE:
            await update.message.reply_text("❌ Магазин не выбран.")
            return
        store_id = MASTER_ADMIN_SELECTED_STORE[user_id]
    else:
        # Для админа магазина используем его store_id
        store_id = admin[4] if len(admin) > 4 else None
        if not store_id:
            await update.message.reply_text("❌ Ошибка: магазин не назначен.")
            return

    store = get_store(store_id)
    if not store:
        await update.message.reply_text("❌ Магазин не найден.")
        return

    conn = sqlite3.connect('fasoley_bot.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM user_coupons uc
        JOIN promotions p ON uc.promotion_id = p.id
        WHERE p.store_id = ?
    """, (store_id,))
    store_coupons = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM user_coupons uc
        JOIN promotions p ON uc.promotion_id = p.id
        WHERE p.store_id = ? AND uc.redeemed = 1
    """, (store_id,))
    store_redeemed = cursor.fetchone()[0]
    percentage = round((store_redeemed / store_coupons * 100), 1) if store_coupons else 0
    stats_text = (
        f"📊 СТАТИСТИКА МАГАЗИНА\n\n"
        f"🏪 {store['name']}\n"
        f"📍 {store['address']}, {store['city']}\n\n"
        f"🎁 Выдано купонов: {store_coupons}\n"
        f"✅ Погашено купонов: {store_redeemed}\n"
        f"📈 Процент погашения: {percentage}%"
    )
    conn.close()
    await update.message.reply_text(stats_text)

async def show_general_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Общая статистика для мастер-админа с изменением клавиатуры"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Сначала войдите в админ-панель как мастер-админ")
        return

    conn = get_db_connection() # Используем функцию из database.py для получения соединения
    cursor = conn.cursor()
    
    # --- Существующая статистика ---
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM user_coupons")
    total_coupons = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM user_coupons WHERE redeemed = 1")
    redeemed_coupons = cursor.fetchone()[0]
    percentage = round((redeemed_coupons / total_coupons * 100), 1) if total_coupons else 0
    
    # --- Статистика за текущий месяц ---
    current_month = datetime.now().month
    current_year = datetime.now().year
    cursor.execute("""
        SELECT COUNT(*) FROM user_coupons 
        WHERE strftime('%Y-%m', created_at) = ?
    """, (f"{current_year}-{current_month:02d}",))
    monthly_issued = cursor.fetchone()[0]
    cursor.execute("""
        SELECT COUNT(*) FROM user_coupons 
        WHERE strftime('%Y-%m', created_at) = ? AND redeemed = 1
    """, (f"{current_year}-{current_month:02d}",))
    monthly_redeemed = cursor.fetchone()[0]
    monthly_percentage = round((monthly_redeemed / monthly_issued * 100), 1) if monthly_issued else 0

    # --- НОВАЯ СТАТИСТИКА ---
    # Количество магазинов
    cursor.execute("SELECT COUNT(*) FROM stores")
    total_stores = cursor.fetchone()[0]

    # Количество активных акций
    # Активная акция - это акция, которая активна на текущую дату
    today_str = datetime.now().date().isoformat()
    cursor.execute("""
        SELECT COUNT(*) FROM promotions 
        WHERE date(?) BETWEEN start_date AND date(start_date, '+' || duration || ' days')
    """, (today_str,))
    active_promotions = cursor.fetchone()[0]
    # --- КОНЕЦ НОВОЙ СТАТИСТИКИ ---
    
    stats_text = (
        f"📊 <b>ОБЩАЯ СТАТИСТИКА</b>\n"
        f"🏪 Всего магазинов: {total_stores}\n"
        f"🎁 Всего активных акций: {active_promotions}\n"
        f"👥 Всего пользователей: {total_users}\n\n"
        f"📊 <b>СТАТИСТИКА ПО КУПОНАМ</b>\n"
        f"🎁 Всего выдано купонов: {total_coupons}\n"
        f"✅ Всего погашено: {redeemed_coupons}\n"
        f"📈 Процент погашения: {percentage}%\n\n"
        f"📅 <b>ЗА ТЕКУЩИЙ МЕСЯЦ:</b>\n"
        f"🎁 Выдано купонов: {monthly_issued}\n"
        f"✅ Погашено: {monthly_redeemed}\n\n"
        f"📈 Процент погашения: {monthly_percentage}%"
    )
    conn.close()
    
    # Меняем клавиатуру - заменяем "Общая статистика" на "Статистика по магазинам"
    keyboard = [
        [KeyboardButton("📊 Статистика по магазинам"), KeyboardButton("🎁 Управление акциями")],
        [KeyboardButton("🔙 Выйти из админки")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    # Сохраняем состояние, что мастер смотрит статистику
    MASTER_VIEWING_STATS[user_id] = True
    await update.message.reply_text(stats_text, parse_mode="HTML", reply_markup=reply_markup)

async def show_store_stats_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список магазинов со статистикой за текущий месяц"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return

    stores = get_stores()
    
    if not stores:
        await update.message.reply_text("❌ Магазины не найдены.")
        return

    stats_text = "📊 СТАТИСТИКА ПО МАГАЗИНАМ (текущий месяц)\n\n"
    
    for store in stores:
        store_stats = get_store_stats_for_current_month(store['id'])
        
        stats_text += (
            f"🏪 <b>{store['city']}, {store['address']}</b>\n"
            f"👥 Пользователей: {store_stats['users_count']}\n"
            f"🎁 Активных акций: {store_stats['active_promotions']}\n"
            f"📨 Выдано купонов: {store_stats['issued_coupons']}\n"
            f"✅ Погашено: {store_stats['redeemed_coupons']}\n"
            f"📈 Процент: {store_stats['redemption_rate']}%\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
        )

    # Возвращаем обычную клавиатуру мастер-админа
    keyboard = [
        [KeyboardButton("📊 Общая статистика"), KeyboardButton("🎁 Управление акциями")],
        [KeyboardButton("🔙 Выйти из админки")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # Убираем состояние просмотра статистики
    if user_id in MASTER_VIEWING_STATS:
        del MASTER_VIEWING_STATS[user_id]
    
    await update.message.reply_text(stats_text, parse_mode="HTML", reply_markup=reply_markup)    

def get_store_stats_for_current_month(store_id):
    """Получить статистику по магазину за текущий месяц"""
    conn = sqlite3.connect('fasoley_bot.db')
    cursor = conn.cursor()
    
    # Текущий месяц и год в формате YYYY-MM
    current_date = datetime.now()
    current_month_str = current_date.strftime('%Y-%m')
    
    # Количество пользователей, привязанных к магазину
    cursor.execute("SELECT COUNT(*) FROM users WHERE store_id = ?", (store_id,))
    users_count = cursor.fetchone()[0]
    
    # Количество активных акций (акции, активные на текущий момент)
    cursor.execute("""
        SELECT COUNT(*) FROM promotions 
        WHERE store_id = ? AND 
              date('now') BETWEEN start_date AND date(start_date, '+' || duration || ' days')
    """, (store_id,))
    active_promotions = cursor.fetchone()[0]
    
    # Количество выданных купонов за текущий месяц
    cursor.execute("""
        SELECT COUNT(*) FROM user_coupons uc
        JOIN promotions p ON uc.promotion_id = p.id
        WHERE p.store_id = ? AND 
              strftime('%Y-%m', uc.created_at) = ?
    """, (store_id, current_month_str))
    issued_coupons = cursor.fetchone()[0]
    
    # Количество погашенных купонов за текущий месяц
    cursor.execute("""
        SELECT COUNT(*) FROM user_coupons uc
        JOIN promotions p ON uc.promotion_id = p.id
        WHERE p.store_id = ? AND 
              strftime('%Y-%m', uc.created_at) = ? AND 
              uc.redeemed = 1
    """, (store_id, current_month_str))
    redeemed_coupons = cursor.fetchone()[0]
    
    # Процент погашения
    redemption_rate = round((redeemed_coupons / issued_coupons * 100), 1) if issued_coupons else 0
    
    conn.close()
    
    return {
        'users_count': users_count,
        'active_promotions': active_promotions,
        'issued_coupons': issued_coupons,
        'redeemed_coupons': redeemed_coupons,
        'redemption_rate': redemption_rate
    }

async def show_my_promotions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать акции (для админа магазина или мастер-админа для выбранного магазина)"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS:
        await update.message.reply_text("❌ Сначала войдите в админ-панель")
        return

    admin = ADMIN_SESSIONS[user_id]
    role = admin[3]

    if role == "master":
        if user_id not in MASTER_ADMIN_SELECTED_STORE:
            await update.message.reply_text("❌ Магазин не выбран.")
            return
        store_id = MASTER_ADMIN_SELECTED_STORE[user_id]
        # ИСПРАВЛЕНО: используем новую функцию с локальными ID
        promotions = get_promotions_with_local_ids(store_id)
        store = get_store(store_id)
        title = f"🎁 <b>Акции магазина {store['name']}</b>"
    else:
        store_id = admin[4] if len(admin) > 4 else None
        # ИСПРАВЛЕНО: используем новую функцию с локальными ID
        promotions = get_promotions_with_local_ids(store_id)
        store = get_store(store_id)
        title = f"🎁 <b>Акции магазина {store['name']}</b>"

    if not promotions:
        await update.message.reply_text("📝 Акций пока нет")
        if role == "master" and user_id in MASTER_ADMIN_SELECTED_STORE:
             await show_selected_store_menu(update, context, store_id)
        return

    # Подключаемся к БД для подсчета выданных и погашенных купонов
    conn = sqlite3.connect('fasoley_bot.db')
    cursor = conn.cursor()
    
    promo_text = f"{title}\n\n"
    for promo in promotions:
        # ИСПРАВЛЕНО: используем локальный ID для отображения
        local_id = promo['local_id']  # Локальный ID для отображения
        promo_id = promo['id']        # Глобальный ID для запросов к БД
        description = promo['description']
        start_date = promo['start_date']
        duration = promo['duration']
        max_coupons = promo['max_coupons']
        valid_days = promo['valid_days']
        starts_today = promo['starts_today']
        
        # ПОДСЧЕТ ВЫДАННЫХ КУПОНОВ ДЛЯ ЭТОЙ АКЦИИ
        cursor.execute("""
            SELECT COUNT(*) FROM user_coupons 
            WHERE promotion_id = ?
        """, (promo_id,))
        issued_coupons = cursor.fetchone()[0]
        
        # ПОДСЧЕТ ПОГАШЕННЫХ КУПОНОВ ДЛЯ ЭТОЙ АКЦИИ
        cursor.execute("""
            SELECT COUNT(*) FROM user_coupons 
            WHERE promotion_id = ? AND redeemed = 1
        """, (promo_id,))
        redeemed_coupons = cursor.fetchone()[0]
        
        # РАСЧЕТ ПРОЦЕНТА ПОГАШЕНИЯ
        redemption_percentage = round((redeemed_coupons / issued_coupons * 100), 1) if issued_coupons else 0
        
        try:
            start_dt = datetime.strptime(start_date, '%d.%m.%Y').date()
        except ValueError:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                continue
        
        end_dt = start_dt + timedelta(days=duration)
        today = datetime.now().date()
        status = "🟢 Активна" if start_dt <= today <= end_dt else "🔴 Неактивна"
        
        # Определяем тип старта для отображения
        start_type = "День в день" if starts_today else "На следующий день"
        
        # ОБНОВЛЕННАЯ ИНФОРМАЦИЯ С ЛОКАЛЬНЫМ ID
        promo_text += (
            f"ID: {local_id}\n"  # ИСПРАВЛЕНО: показываем локальный ID
            f"🎁 Описание: {description}\n"
            f"📅 Период акции: {start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')}\n"
            f"⏰ Тип старта: {start_type}\n"
            f"📊 Макс. купонов: {max_coupons if max_coupons > 0 else '∞'}\n"
            f"📨 Выдано купонов: {issued_coupons}\n"
            f"✅ Погашено: {redeemed_coupons}\n"
            f"📈 Процент погашения: {redemption_percentage}%\n"
            f"⏳ Срок действия купона: {valid_days} дн.\n"
            f"📊 Статус: {status}\n"
            "━━━━━━━━━━━━━━━━\n"
        )
    
    conn.close()
    
    await update.message.reply_text(text=promo_text, parse_mode="HTML")
    
    # Для мастер-админа после показа списка акций показываем меню управления
    if role == "master" and user_id in MASTER_ADMIN_SELECTED_STORE:
         await show_selected_store_menu(update, context, store_id)

async def add_promotion_start_for_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления акции мастер-админом для выбранного магазина"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return
        
    if user_id not in MASTER_ADMIN_SELECTED_STORE:
        await update.message.reply_text("❌ Магазин не выбран.")
        return
        
    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "📝 ДОБАВЛЕНИЕ АКЦИИ\n\n"
        "Шаг 1 из 6: Введите описание акции\n"
        "Например: 🍫 Шоколадка Snickers в подарок",
        reply_markup=reply_markup
    )
    USER_STATES[user_id] = "adding_promotion_description"

async def delete_promotion_start_for_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления акции мастер-админом из выбранного магазина с локальными ID"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return
        
    if user_id not in MASTER_ADMIN_SELECTED_STORE:
        await update.message.reply_text("❌ Магазин не выбран.")
        return
        
    store_id = MASTER_ADMIN_SELECTED_STORE[user_id]
    # ИСПРАВЛЕНО: используем новую функцию с локальными ID
    promotions = get_promotions_with_local_ids(store_id)

    if not promotions:
        await update.message.reply_text("❌ Нет акций для удаления")
        return

    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    promo_text = "❌ УДАЛЕНИЕ АКЦИИ\n\nВведите ЛОКАЛЬНЫЙ ID акции для удаления:\n\n"
    for promo in promotions:
        local_id = promo['local_id']  # ИСПРАВЛЕНО: используем локальный ID
        description = promo['description']
        promo_text += f"ID: {local_id} - {description}\n"
    await update.message.reply_text(promo_text, reply_markup=reply_markup)
    USER_STATES[user_id] = "deleting_promotion"

async def add_promotion_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления акции (для админа магазина)"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS:
        await update.message.reply_text("❌ Сначала войдите в админ-панель")
        return

    admin = ADMIN_SESSIONS[user_id]
    role = admin[3]

    if role == "master":
        # Перенаправляем на специальную функцию для мастер-админа
        await add_promotion_start_for_master(update, context)
        return

    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "📝 ДОБАВЛЕНИЕ АКЦИИ\n\n"
        "Шаг 1 из 6: Введите описание акции\n"
        "Например: 🍫 Шоколадка Snickers в подарок",
        reply_markup=reply_markup
    )
    USER_STATES[user_id] = "adding_promotion_description"

async def delete_promotion_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления акции (для админа магазина) с локальными ID"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS:
        await update.message.reply_text("❌ Сначала войдите в админ-панель")
        return

    admin = ADMIN_SESSIONS[user_id]
    role = admin[3]

    if role == "master":
        await delete_promotion_start_for_master(update, context)
        return
        
    store_id = admin[4] if len(admin) > 4 else None
    # ИСПРАВЛЕНО: используем новую функцию с локальными ID
    promotions = get_promotions_with_local_ids(store_id)

    if not promotions:
        await update.message.reply_text("❌ Нет акций для удаления")
        return

    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    promo_text = "❌ УДАЛЕНИЕ АКЦИИ\n\nВведите ЛОКАЛЬНЫЙ ID акции для удаления:\n\n"
    for promo in promotions:
        local_id = promo['local_id']  # ИСПРАВЛЕНО: используем локальный ID
        description = promo['description']
        promo_text += f"ID: {local_id} - {description}\n"
    await update.message.reply_text(promo_text, reply_markup=reply_markup)
    USER_STATES[user_id] = "deleting_promotion"

# ========== НОВЫЕ ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ МАГАЗИНАМИ ==========

async def manage_stores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление магазинами для мастер-админа"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return

    keyboard = [
        [KeyboardButton("➕ Добавить магазин"), KeyboardButton("🗑 Удалить магазин")],
        [KeyboardButton("📋 Список магазинов"), KeyboardButton("🔙 Назад")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🏪 УПРАВЛЕНИЕ МАГАЗИНАМИ\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def add_store_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления магазина"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return

    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🏪 ДОБАВЛЕНИЕ МАГАЗИНА\n\n"
        "Шаг 1 из 5: Введите город магазина\n"
        "Например: Москва",
        reply_markup=reply_markup
    )
    USER_STATES[user_id] = "adding_store_city"

async def delete_store_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления магазина"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return

    stores = get_stores()
    if not stores:
        await update.message.reply_text("❌ Нет магазинов для удаления")
        return

    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    store_text = "🗑 УДАЛЕНИЕ МАГАЗИНА\n\nВведите ID магазина для удаления:\n\n"
    for store in stores:
        store_text += f"ID: {store['id']} - {store['city']}, {store['address']} ({store['name']})\n"
    
    await update.message.reply_text(store_text, reply_markup=reply_markup)
    USER_STATES[user_id] = "deleting_store"

async def list_stores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список всех магазинов"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return

    stores = get_stores()
    if not stores:
        await update.message.reply_text("📝 Магазинов пока нет")
        return

    store_text = "📋 СПИСОК МАГАЗИНОВ\n\n"
    for store in stores:
        # Получаем информацию об администраторе магазина
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT login FROM admins WHERE store_id = ? AND role = 'store'", (store['id'],))
        admin = cursor.fetchone()
        conn.close()
        
        admin_login = admin['login'] if admin else "❌ Не назначен"
        
        store_text += (
            f"🏪 <b>ID: {store['id']}</b>\n"
            f"🏙 Город: {store['city']}\n"
            f"📍 Адрес: {store['address']}\n"
            f"📛 Название: {store['name']}\n"
            f"👨‍💼 Админ: {admin_login}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
        )

    await update.message.reply_text(store_text, parse_mode="HTML")

async def cancel_current_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    user_id = update.effective_user.id
    if user_id in USER_STATES:
        del USER_STATES[user_id]
    # Не очищаем MASTER_ADMIN_SELECTED_STORE здесь, чтобы пользователь мог вернуться к меню магазина
    context.user_data.clear()
    if user_id in ADMIN_SESSIONS:
        admin = ADMIN_SESSIONS[user_id]
        await show_admin_panel(update, context, admin)
    else:
        await start(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # --- Обработка клавиатурной кнопки "Назад" ---
    if text == "🔙 Назад":
        # Проверяем, в каком состоянии находится пользователь
        if user_id in USER_STATES:
            state = USER_STATES[user_id]
            
            # --- Логика для админов ---
            if user_id in ADMIN_SESSIONS:
                admin = ADMIN_SESSIONS[user_id]
                role = admin[3]
                
                # Если пользователь находился на этапе входа админа
                if state == "waiting_admin_credentials":
                    if user_id in USER_STATES:
                        del USER_STATES[user_id]
                    await start(update, context)
                    return
                    
                # Если пользователь находился на этапе погашения купона
                elif state == "redeeming_coupon":
                    if user_id in USER_STATES:
                        del USER_STATES[user_id]
                    await start(update, context)
                    return
                    
                # Если пользователь находился на этапе добавления акции
                elif state in ["adding_promotion_description", "adding_promotion_date", "adding_promotion_duration", "adding_promotion_max_coupons", "adding_promotion_valid_days", "adding_promotion_start_type"]:
                    if user_id in USER_STATES:
                        del USER_STATES[user_id]
                    # Возвращаем в админ-панель
                    await show_admin_panel(update, context, admin)
                    return
                    
                # Если пользователь находился на этапе удаления акции
                elif state == "deleting_promotion":
                    if user_id in USER_STATES:
                        del USER_STATES[user_id]
                    # Возвращаем в админ-панель
                    await show_admin_panel(update, context, admin)
                    return
                    
                # Если пользователь мастер-админ и находится в процессе выбора магазина
                elif role == "master" and user_id not in MASTER_ADMIN_SELECTED_STORE:
                     if user_id in USER_STATES:
                        del USER_STATES[user_id]
                     # Возвращаем в мастер-панель
                     await show_admin_panel(update, context, admin)
                     return
                     
                # Если пользователь мастер-админ и находится в меню выбранного магазина
                elif role == "master" and user_id in MASTER_ADMIN_SELECTED_STORE:
                     if user_id in USER_STATES:
                        del USER_STATES[user_id]
                     # Возвращаем в меню выбора магазина
                     store_id = MASTER_ADMIN_SELECTED_STORE[user_id]
                     await show_selected_store_menu(update, context, store_id)
                     return
                
                # === НОВАЯ ЛОГИКА ДЛЯ УПРАВЛЕНИЯ МАГАЗИНАМИ ===
                elif state in ["adding_store_city", "adding_store_address", "adding_store_name", 
                              "adding_store_admin_login", "adding_store_admin_password", 
                              "deleting_store", "confirm_store_deletion"]:
                    if user_id in USER_STATES:
                        del USER_STATES[user_id]
                    await manage_stores(update, context)
                    return
                # === КОНЕЦ НОВОЙ ЛОГИКИ ===
                     
                # Для всех остальных состояний админа просто удаляем состояние и возвращаем в админ-панель
                else:
                    if user_id in USER_STATES:
                        del USER_STATES[user_id]
                    await show_admin_panel(update, context, admin)
                    return
            else:
                # Если пользователь не админ, просто удаляем состояние и возвращаем в главное меню
                if user_id in USER_STATES:
                    del USER_STATES[user_id]
                await start(update, context)
                return
        else:
          # Если пользователь не в состоянии, но является мастером и смотрит статистику
            if user_id in MASTER_VIEWING_STATS:
                # Возвращаем обычную клавиатуру мастер-админа
                keyboard = [
                    [KeyboardButton("📊 Общая статистика"), KeyboardButton("🎁 Управление акциями")],
                    [KeyboardButton("🔙 Выйти из админки")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text("Главное меню мастер-админа:", reply_markup=reply_markup)
                del MASTER_VIEWING_STATS[user_id]
                return
            # Если пользователь не в состоянии, проверяем, не админ ли он
            if user_id in ADMIN_SESSIONS:
                admin = ADMIN_SESSIONS[user_id]
                await show_admin_panel(update, context, admin)
            else:
                await start(update, context)
            return

    # Обработка кнопок отмены (если они остались где-то)
    if text in ["🔙 Отменить вход", "🔙 Отменить добавление", "🔙 Отменить удаление", "🔙 Отменить погашение"]:
        await cancel_current_action(update, context)
        return
        
    # Обработка кнопки "Назад к выбору магазина" в меню управления магазином мастер-админа
    if text == "🔙 Назад к выбору магазина":
         if user_id in MASTER_ADMIN_SELECTED_STORE:
            del MASTER_ADMIN_SELECTED_STORE[user_id]
         await choose_admin_store(update, context)
         return

    # Обработка состояний
    if user_id in USER_STATES:
        state = USER_STATES[user_id]
        if state == "waiting_admin_credentials":
            # Разбиваем ввод на 2 части: логин и всё остальное как пароль
            parts = text.split(' ', 1)

            # 1) Проверка формата: должны быть ДВЕ непустые части
            if len(parts) < 2:
                keyboard = [[KeyboardButton("🔙 Назад")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    "❌ Введите логин и пароль через пробел\nНапример: admin password",
                    reply_markup=reply_markup
                )
                return

            login = parts[0].strip()
            password = parts[1].strip()

            if not login or not password:
                keyboard = [[KeyboardButton("🔙 Назад")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    "❌ Логин и пароль не должны быть пустыми\nПовторите ввод: login password",
                    reply_markup=reply_markup
                )
                return

            # 2) Проверяем креды
            admin = get_admin(login, password)

            if admin:
                # Успех — выходим из состояния и открываем панель
                if user_id in USER_STATES:
                    del USER_STATES[user_id]
                await show_admin_panel(update, context, admin)
                return

            # 3) Неверные креды — остаёмся в состоянии и предлагаем повтор
            keyboard = [[KeyboardButton("🔙 Назад")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "❌ Неверный логин или пароль.\nПопробуйте ещё раз: введите логин и пароль через пробел",
                reply_markup=reply_markup
            )
            return

        elif state == "redeeming_coupon":
            if not text.isdigit() or len(text) != 6:
                await update.message.reply_text("❌ Введите корректный 6-значный код")
                return
            
            # Отладочная информация
            logger.info(f"Попытка погашения купона: {text} пользователем: {user_id}")
            
            result = redeem_coupon_by_code(text, user_id)
            
            # Отладочная информация
            logger.info(f"Результат погашения: {result}")
            
            # Проверяем статус результата
            status = result.get("status")
            if status == "not_found":
                await update.message.reply_text("❌ Купон не найден")
            elif status == "expired":
                await update.message.reply_text("❌ Купон просрочен")
            elif status == "success":
                success_msg = (
                    f"✅ КУПОН УСПЕШНО ПОГАШЕН!\n\n"
                    f"🎁 Акция: {result['description']}\n"
                    f"🏪 Магазин: {result['store_name']}\n"
                    f"📍 Адрес: {result['address']}, {result['city']}\n"
                    f"🔢 Код: {result['code']}"
                )
                await update.message.reply_text(success_msg)
                
                # Отправляем уведомление владельцу купона, если это не тот же пользователь
                owner_telegram_id = result['owner_telegram_id']
                if owner_telegram_id != user_id:
                    try:
                        owner_notification = (
                            f"📣 ВАШ КУПОН БЫЛ ПОГАШЕН!\n\n"
                            f"🎁 Акция: {result['description']}\n"
                            f"🏪 Магазин: {result['store_name']}\n"
                            f"📍 Адрес: {result['address']}, {result['city']}\n"
                            f"🔢 Код: {result['code']}\n"
                        )
                        await context.bot.send_message(
                            chat_id=owner_telegram_id,
                            text=owner_notification
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление владельцу купона {owner_telegram_id}: {e}")
            
            del USER_STATES[user_id]
            #await start(update, context)
            
        elif state == "adding_promotion_description":
            context.user_data['promo_description'] = text
            keyboard = [[KeyboardButton("🔙 Назад")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "📅 Шаг 2 из 6: Введите дату начала акции\n"
                "Формат: ДД.ММ.ГГГГ\n"
                "Например: 22.08.2025",
                reply_markup=reply_markup
            )
            USER_STATES[user_id] = "adding_promotion_date"
        elif state == "adding_promotion_date":
            try:
                datetime.strptime(text, '%d.%m.%Y')
                context.user_data['promo_start_date'] = text
                keyboard = [[KeyboardButton("🔙 Назад")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    "⏰ Шаг 3 из 6: Введите продолжительность акции в днях\n"
                    "Например: 7",
                    reply_markup=reply_markup
                )
                USER_STATES[user_id] = "adding_promotion_duration"
            except ValueError:
                await update.message.reply_text("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ")
        elif state == "adding_promotion_duration":
            try:
                duration = int(text)
                if duration <= 0:
                    raise ValueError
                context.user_data['promo_duration'] = duration
                keyboard = [[KeyboardButton("🔙 Назад")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                # НОВЫЙ ШАГ: Запрос макс. количества купонов
                await update.message.reply_text(
                    "📊 Шаг 4 из 6: Введите максимальное количество купонов по этой акции\n"
                    "Введите 0, если лимит не нужен (безлимитная акция)\n"
                    "Например: 100",
                    reply_markup=reply_markup
                )
                USER_STATES[user_id] = "adding_promotion_max_coupons"
            except ValueError:
                await update.message.reply_text("❌ Введите число (количество дней)")
        elif state == "adding_promotion_max_coupons":
            try:
                max_coupons = int(text)
                if max_coupons < 0:
                    raise ValueError
                context.user_data['promo_max_coupons'] = max_coupons
                keyboard = [[KeyboardButton("🔙 Назад")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                # НОВЫЙ ШАГ: Запрос срока действия купона
                await update.message.reply_text(
                    "⏰ Шаг 5 из 6: Введите количество дней, в течение которых купон будет действителен после получения\n"
                    "Например: 3",
                    reply_markup=reply_markup
                )
                USER_STATES[user_id] = "adding_promotion_valid_days"
            except ValueError:
                await update.message.reply_text("❌ Введите число (0 или больше)")
        elif state == "adding_promotion_valid_days":
            try:
                valid_days = int(text)
                if valid_days <= 0:
                    raise ValueError

                context.user_data['promo_valid_days'] = valid_days
                keyboard = [
                    [KeyboardButton("✅ День в день"), KeyboardButton("⏳ На следующий день")],
                    [KeyboardButton("🔙 Назад")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                # НОВЫЙ ШАГ: Выбор типа старта акции
                await update.message.reply_text(
                    "🚀 Шаг 6 из 6: Выберите, когда акция становится доступной для использования:\n\n"
                    "✅ День в день - пользователь может воспользоваться акцией сразу после получения\n"
                    "⏳ На следующий день - пользователь сможет воспользоваться акцией только со следующего дня",
                    reply_markup=reply_markup
                )
                USER_STATES[user_id] = "adding_promotion_start_type"
            except ValueError:
                await update.message.reply_text("❌ Введите число (количество дней, больше 0)")
        
        elif state == "adding_promotion_start_type":
            # Обработка выбора типа старта
            if text in ["✅ День в день", "⏳ На следующий день"]:
                starts_today = 1 if text == "✅ День в день" else 0
                
                # Получаем все собранные данные
                admin = ADMIN_SESSIONS[user_id]
                role = admin[3]
                description = context.user_data['promo_description']
                start_date = context.user_data['promo_start_date']
                duration = context.user_data['promo_duration']
                max_coupons = context.user_data['promo_max_coupons']
                valid_days = context.user_data['promo_valid_days']

                if role == "master":
                    if user_id not in MASTER_ADMIN_SELECTED_STORE:
                        await update.message.reply_text("❌ Ошибка: магазин не выбран.")
                        del USER_STATES[user_id]
                        return
                    store_id = MASTER_ADMIN_SELECTED_STORE[user_id]
                else:
                    store_id = admin[4] if len(admin) > 4 else None

                # СОЗДАЕМ акцию с ВСЕМИ параметрами, включая starts_today
                create_promotion(store_id, description, start_date, duration, max_coupons, valid_days, starts_today)
                store = get_store(store_id)
                
                start_type_text = "день в день" if starts_today else "на следующий день"
                success_msg = (f"✅ Акция успешно создана!\n\n"
                               f"🏪 Магазин: {store['name']}\n"
                               f"🎁 Акция: {description}\n"
                               f"📅 Длительность акции: {duration} дн.\n"
                               f"📊 Макс. купонов: {max_coupons if max_coupons > 0 else '∞'}\n"
                               f"⏳ Срок действия купона: {valid_days} дн.\n"
                               f"🚀 Старт акции: {start_type_text}")
                
                del USER_STATES[user_id]
                if role == "master":
                    await show_selected_store_menu(update, context, store_id)
                else:
                    await update.message.reply_text(success_msg)
            else:
                await update.message.reply_text("❌ Пожалуйста, выберите один из предложенных вариантов")
                
        elif state == "deleting_promotion":
            try:
                local_id = int(text)  # Локальный ID, который ввел пользователь
                
                # Получаем информацию о текущем магазине
                admin = ADMIN_SESSIONS[user_id]
                role = admin[3]
                
                if role == "master":
                    if user_id not in MASTER_ADMIN_SELECTED_STORE:
                        await update.message.reply_text("❌ Ошибка: магазин не выбран.")
                        del USER_STATES[user_id]
                        return
                    store_id = MASTER_ADMIN_SELECTED_STORE[user_id]
                else:
                    store_id = admin[4] if len(admin) > 4 else None

                # ИСПРАВЛЕНО: находим глобальный ID по локальному
                promotions = get_promotions_with_local_ids(store_id)
                target_promo = None
                
                for promo in promotions:
                    if promo['local_id'] == local_id:
                        target_promo = promo
                        break
                
                if not target_promo:
                    await update.message.reply_text("❌ Акция с таким локальным ID не найдена")
                    return
                    
                global_id = target_promo['id']  # Настоящий ID для операции в БД

                # Проверяем существование акции (дополнительная проверка)
                conn = sqlite3.connect('fasoley_bot.db')
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM promotions WHERE id = ? AND store_id = ?", (global_id, store_id))
                promo = cursor.fetchone()
                if not promo:
                    await update.message.reply_text("❌ Акция не найдена или у вас нет прав на её удаление")
                    conn.close()
                    return
                    
                # Удаляем по глобальному ID
                cursor.execute("DELETE FROM promotions WHERE id = ?", (global_id,))
                conn.commit()
                conn.close()
                
                success_msg = f"✅ Акция ID:{local_id} успешно удалена!"
                del USER_STATES[user_id]
                
                # Возвращаем в соответствующее меню
                if role == "master":
                    await show_selected_store_menu(update, context, store_id)
                else:
                    # Для store-admin просто отправляем сообщение об успехе
                    await update.message.reply_text(success_msg)
                    
            except ValueError:
                await update.message.reply_text("❌ Введите корректный ЛОКАЛЬНЫЙ ID акции (число)")

        # ========== НОВЫЕ СОСТОЯНИЯ ДЛЯ УПРАВЛЕНИЯ МАГАЗИНАМИ ==========
        elif state == "adding_store_city":
            context.user_data['store_city'] = text
            await update.message.reply_text(
                "📍 Шаг 2 из 5: Введите адрес магазина\n"
                "Например: ул. Ленина, 15"
            )
            USER_STATES[user_id] = "adding_store_address"

        elif state == "adding_store_address":
            context.user_data['store_address'] = text
            await update.message.reply_text(
                "📛 Шаг 3 из 5: Введите название магазина\n"
                "Например: Фасоль Москва-3"
            )
            USER_STATES[user_id] = "adding_store_name"

        elif state == "adding_store_name":
            context.user_data['store_name'] = text
            await update.message.reply_text(
                "👨‍💼 Шаг 4 из 5: Введите логин для администратора магазина\n"
                "Например: m3"
            )
            USER_STATES[user_id] = "adding_store_admin_login"

        elif state == "adding_store_admin_login":
            context.user_data['store_admin_login'] = text
            await update.message.reply_text(
                "🔐 Шаг 5 из 5: Введите пароль для администратора магазина\n"
                "Например: m3"
            )
            USER_STATES[user_id] = "adding_store_admin_password"

        elif state == "adding_store_admin_password":
            # Получаем все данные
            city = context.user_data['store_city']
            address = context.user_data['store_address']
            name = context.user_data['store_name']
            login = context.user_data['store_admin_login']
            password = text

            # Создаем магазин
            store_id = create_store(city, address, name)
            
            if store_id is None:
                await update.message.reply_text("❌ Магазин с такими данными уже существует!")
                del USER_STATES[user_id]
                await manage_stores(update, context)
                return

            # Создаем администратора
            admin_created = create_store_admin(login, password, store_id)
            
            if not admin_created:
                # Если не удалось создать администратора, удаляем магазин
                delete_store(store_id)
                await update.message.reply_text("❌ Логин администратора уже занят!")
                del USER_STATES[user_id]
                await manage_stores(update, context)
                return

            success_msg = (
                f"✅ Магазин успешно создан!\n\n"
                f"🏙 Город: {city}\n"
                f"📍 Адрес: {address}\n"
                f"📛 Название: {name}\n"
                f"🆔 ID магазина: {store_id}\n"
                f"👨‍💼 Логин админа: {login}\n"
                f"🔐 Пароль админа: {password}"
            )
            
            # Очищаем состояние и данные
            del USER_STATES[user_id]
            context.user_data.clear()
            
            await update.message.reply_text(success_msg)
            await manage_stores(update, context)

        elif state == "deleting_store":
            try:
                store_id = int(text)
                store = get_store(store_id)
                
                if not store:
                    await update.message.reply_text("❌ Магазин не найден")
                    return
                
                # Подтверждение удаления
                keyboard = [
                    [KeyboardButton("✅ Да, удалить"), KeyboardButton("❌ Нет, отменить")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                confirmation_text = (
                    f"⚠️ ВЫ УДАЛЯЕТЕ МАГАЗИН:\n\n"
                    f"🏙 Город: {store['city']}\n"
                    f"📍 Адрес: {store['address']}\n"
                    f"📛 Название: {store['name']}\n\n"
                    f"Это действие нельзя отменить!\n"
                    f"Удалить магазин?"
                )
                
                context.user_data['store_to_delete'] = store_id
                await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
                USER_STATES[user_id] = "confirm_store_deletion"
                
            except ValueError:
                await update.message.reply_text("❌ Введите корректный ID магазина")

        elif state == "confirm_store_deletion":
            if text == "✅ Да, удалить":
                store_id = context.user_data.get('store_to_delete')
                if store_id:
                    success = delete_store(store_id)
                    if success:
                        await update.message.reply_text("✅ Магазин успешно удален!")
                    else:
                        await update.message.reply_text("❌ Ошибка при удалении магазина")
            else:
                await update.message.reply_text("❌ Удаление отменено")
            
            # Очищаем состояние и данные
            del USER_STATES[user_id]
            context.user_data.clear()
            await manage_stores(update, context)
        # ========== КОНЕЦ НОВЫХ СОСТОЯНИЙ ==========
        return

    # Обработка кнопок меню
    if text == "🏪 Выбрать магазин" or text == "🔄 Сменить магазин":
        await choose_store(update, context)
    elif text == "🎁 Получить акцию":
        await get_promotion(update, context)
    elif text == "📱 Мои купоны":
        await my_coupons(update, context)
    elif text == "🏪 Мой магазин":
        await my_store(update, context)
    elif text == "👨‍💼 Вход для администратора":
        await admin_login(update, context)
    elif text == "💳 Погасить купон (для продавцов)":
        await redeem_coupon_start(update, context)
    elif text == "🔙 Выйти из админки":
        if user_id in ADMIN_SESSIONS:
            del ADMIN_SESSIONS[user_id]
        if user_id in USER_STATES:
            del USER_STATES[user_id]
        if user_id in MASTER_ADMIN_SELECTED_STORE:
            del MASTER_ADMIN_SELECTED_STORE[user_id]
        await start(update, context)

    # Админские кнопки
    elif user_id in ADMIN_SESSIONS:
        admin = ADMIN_SESSIONS[user_id]
        role = admin[3]
        if role == "master":
            if text == "📊 Общая статистика":
                await show_general_stats(update, context)
            elif text == "📊 Статистика по магазинам":
                await show_store_stats_list(update, context)
            elif text == "🎁 Управление акциями":
                await choose_admin_store(update, context)
            # Кнопки внутри меню выбранного магазина
            elif text == "📊 Статистика магазина":
                await show_store_stats_for_master(update, context) # Используем исправленную функцию
            elif text == "🎁 Управление акциями магазина":
                await show_my_promotions(update, context)
            elif text == "➕ Добавить акцию в магазин":
                await add_promotion_start_for_master(update, context)
            elif text == "❌ Удалить акцию из магазина":
                await delete_promotion_start_for_master(update, context)
            # ========== НОВЫЕ КНОПКИ УПРАВЛЕНИЯ МАГАЗИНАМИ ==========
            elif text == "🏪 Управление магазинами":
                await manage_stores(update, context)
            elif text == "➕ Добавить магазин":
                await add_store_start(update, context)
            elif text == "🗑 Удалить магазин":
                await delete_store_start(update, context)
            elif text == "📋 Список магазинов":
                await list_stores(update, context)
            # ========== КОНЕЦ НОВЫХ КНОПОК ==========
        else: # store admin
            if text == "📊 Статистика магазина":
                await show_store_stats_for_master(update, context) # Используем исправленную функцию
            elif text == "🎁 Мои акции":
                await show_my_promotions(update, context)
            elif text == "➕ Добавить акцию":
                await add_promotion_start(update, context)
            elif text == "❌ Удалить акцию":
                await delete_promotion_start(update, context)

# ========== АНИМИРОВАННАЯ РУЛЕТКА АКЦИЙ ==========

async def animated_promotion_roulette(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    store_id = get_user(user_id)
    if not store_id:
        await update.message.reply_text("❌ Сначала выберите магазин!")
        await choose_store(update, context)
        return

    # Проверка лимита: 1 купон в день
    today = datetime.now().date().isoformat()
    conn = sqlite3.connect('fasoley_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,))
    user_row = cursor.fetchone()
    if user_row:
        correct_user_id = user_row[0]
        cursor.execute("SELECT 1 FROM user_coupons WHERE user_id = ? AND DATE(created_at) = ? LIMIT 1", (correct_user_id, today))
        if cursor.fetchone():
            conn.close()
            await update.message.reply_text("❌ Вы уже получили акцию сегодня! Приходите завтра 😊")
            return

    # Получаем активные акции
    promotions = get_promotions(store_id)
    active_promotions = []
    today_date = datetime.now().date()
    for promo in promotions:
        try:
            start_date = datetime.strptime(promo[3], '%d.%m.%Y').date()
        except ValueError:
            try:
                start_date = datetime.strptime(promo[3], '%Y-%m-%d').date()
            except ValueError:
                continue
        end_date = start_date + timedelta(days=promo[4])
        cursor.execute("SELECT COUNT(*) FROM user_coupons WHERE promotion_id = ?", (promo[0],))
        coupons_issued = cursor.fetchone()[0]
        max_allowed = promo[5]
        if start_date <= today_date <= end_date and (max_allowed == 0 or coupons_issued < max_allowed):
            active_promotions.append(promo)
    conn.close()

    if not active_promotions:
        await update.message.reply_text("😔 В данный момент нет активных акций в вашем магазине")
        return

    # === ЭТАП 1: БЫСТРОЕ ВРАЩЕНИЕ — РОВНО 4 СЕКУНДЫ (10 кадров × 0.4 сек) ===
    spin_emojis = ["🎰", "🎯", "🔄", "✨", "⭐", "💫", "🌟", "⚡"]
    animation_pool = active_promotions * 5
    random.shuffle(animation_pool)

    msg = await update.message.reply_text(
        "🎰 *ЗАПУСК АКЦИОННОЙ РУЛЕТКИ*\n🔄 Подбираем лучшие предложения...",
        parse_mode="Markdown"
    )
    await asyncio.sleep(1.0)

    for i in range(10):  # 10 кадров = 4 секунды при задержке 0.4 сек
        promo = random.choice(animation_pool)
        desc = (promo[2][:28] + "...") if len(promo[2]) > 30 else promo[2]
        emoji = spin_emojis[i % len(spin_emojis)]
        spin_text = f"🎰 *РУЛЕТКА АКЦИЙ КРУТИТСЯ...*\n{emoji} *{desc}*"
        try:
            await msg.edit_text(spin_text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Не удалось обновить анимацию: {e}")
        await asyncio.sleep(0.4)

    # === ЭТАП 2: АНИМАЦИЯ ВЫИГРЫША (БЕЗ ИЗМЕНЕНИЙ) ===
    final_promo = random.choice(active_promotions)
    coupon_code = create_coupon(user_id, final_promo)

    color_emojis = [
        "🟥🔴🎈",  # Красный
        "🟧🟠🍊",  # Оранжевый
        "🟨💛🌟",  # Желтый
        "🟩💚🍀",  # Зеленый
        "🟦💙🌀",  # Синий
        "🟪💜☂️",  # Фиолетовый
    ]
    for i in range(7):
        color_combo = color_emojis[i % len(color_emojis)]
        winner_display = (
            f"{color_combo} *ВАШ ПРИЗ* {color_combo}\n"
            f"🎁 *{final_promo[2]}*"
        )
        await msg.edit_text(winner_display, parse_mode="Markdown")
        await asyncio.sleep(0.4)

    # === ЭТАП 3: ФИНАЛЬНОЕ СООБЩЕНИЕ ===
    store = get_store(store_id)
    valid_until = today_date + timedelta(days=final_promo[6])
    starts_today = final_promo[7]
    availability = "✅ Акцией можно воспользоваться уже сейчас!" if starts_today else "⏳ Акцией можно воспользоваться с завтрашнего дня!"

    final_text = (
        f"🎉 Поздравляем! Вы получили акцию в магазине \"Фасоль\":\n"
        f"🎁 <b>{final_promo[2]}</b>\n"
        f"📍 Адрес: {store['address']}\n"
        f"📅 Дата выдачи: {today_date.strftime('%d.%m.%Y')}\n"
        f"⏳ Купон действителен до: {valid_until.strftime('%d.%m.%Y')}\n"
        f"{availability}\n"
        f"🔢 Ваш код купона: <b>{coupon_code}</b>\n"
        f"Покажите этот код на кассе для получения скидки/подарка! 📱"
    )
    await msg.edit_text(final_text, parse_mode="HTML")


# ЗАМЕНЯЕМ старую функцию get_promotion на анимированную версию
async def get_promotion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анимированное получение акции через рулетку"""
    await animated_promotion_roulette(update, context)

# ========== КОНЕЦ АНИМИРОВАННОЙ РУЛЕТКИ ==========


def main():
    """Запуск бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    init_db()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Убираем обработчик Web App Data, так как функционал удален
    # application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))
    application.run_polling()

if __name__ == '__main__':
    main()