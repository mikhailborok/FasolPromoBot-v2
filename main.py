# main.py
import asyncio
import logging
import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InputFile
# Убираем WebAppInfo, так как функционал удален
# from telegram import WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from io import BytesIO
from datetime import datetime, timedelta
import sqlite3
import re
from database import init_db, get_user, create_user, get_stores, get_store, get_promotions, create_promotion, get_user_coupon, create_coupon, redeem_coupon_by_code, get_admin, get_db_connection
from config import BOT_TOKEN

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
        photo_path = "/content/drive/MyDrive/FasolPromoBotQwen/Fasol_logo.png" # Убедитесь, что путь правильный
        
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
        photo_path = "/content/drive/MyDrive/FasolPromoBotQwen/Fasol_logo.png" # Убедитесь, что путь правильный
        
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

# main.py - функция get_promotion

async def get_promotion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение акции"""
    user_id = update.effective_user.id
    store_id = get_user(user_id)
    if not store_id:
        await update.message.reply_text("❌ Сначала выберите магазин!")
        await choose_store(update, context)
        return

    # Проверяем, получал ли пользователь *любой* купон сегодня (погашен или нет)
    today = datetime.now().date().isoformat()
    conn = sqlite3.connect('fasoley_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM user_coupons 
        WHERE user_id = ? AND DATE(created_at) = ?
        LIMIT 1
    """, (user_id, today))
    existing_coupon_today = cursor.fetchone()
    
    if existing_coupon_today:
        conn.close()
        await update.message.reply_text("❌ Вы уже получили акцию сегодня! Приходите завтра 😊")
        return

    promotions = get_promotions(store_id)
    active_promotions = []
    today_date = datetime.now().date()
    
    for promo in promotions:
        # promo[3] - start_date, promo[4] - duration, promo[5] - max_coupons, promo[6] - valid_days
        try:
            start_date = datetime.strptime(promo[3], '%d.%m.%Y').date()
        except ValueError:
            try:
                start_date = datetime.strptime(promo[3], '%Y-%m-%d').date()
            except ValueError:
                continue
        
        end_date = start_date + timedelta(days=promo[4])
        
        # НОВАЯ ПРОВЕРКА: Не превышен ли лимит купонов по акции?
        cursor.execute("""
            SELECT COUNT(*) FROM user_coupons 
            WHERE promotion_id = ?
        """, (promo[0],))
        coupons_issued = cursor.fetchone()[0]
        max_allowed = promo[5] # max_coupons
        
        # Активна, если дата подходит И (лимит не установлен (0) ИЛИ лимит не превышен)
        if start_date <= today_date <= end_date and (max_allowed == 0 or coupons_issued < max_allowed):
            active_promotions.append(promo)

    conn.close() # Закрываем соединение после проверки лимитов

    if not active_promotions:
        await update.message.reply_text("😔 В данный момент нет активных акций в вашем магазине")
        return

    import random
    selected_promo = random.choice(active_promotions)
    coupon_code = create_coupon(user_id, selected_promo)

    store = get_store(store_id)
    # Вычисляем дату, до которой можно погасить купон
    valid_until_date = today_date + timedelta(days=selected_promo[6]) # valid_days
    
    await update.message.reply_text(
        f"🎉 Поздравляем! Вы получили акцию в магазине \"Фасоль\":\n\n"
        f"🎁 {selected_promo[2]}\n"
        f"📍 Адрес: {store['address']}\n"
        f"📅 Дата выдачи: {today_date.strftime('%d.%m.%Y')}\n"
        f"⏳ Купон действителен до: {valid_until_date.strftime('%d.%m.%Y')}\n\n"
        f"🔢 Ваш код купона: <b>{coupon_code}</b>\n"
        f"Покажите этот код на кассе для получения скидки/подарка! 📱",
        parse_mode="HTML"
    )

async def my_coupons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать мои купоны"""
    telegram_id = update.effective_user.id
    store_id = get_user(telegram_id)
    if not store_id:
        await update.message.reply_text("❌ Сначала выберите магазин!")
        return

    conn = sqlite3.connect('fasoley_bot.db')
    cursor = conn.cursor()

    # 🔹 Сначала получаем внутренний user_id из таблицы users по telegram_id
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    user_row = cursor.fetchone()
    if not user_row:
        conn.close()
        await update.message.reply_text("❌ Вы ещё не зарегистрированы в системе. Получите акцию, чтобы появиться в базе.")
        return
    user_id = user_row[0]  # Это users.id

    # 🔹 Теперь ищем купоны по user_id (внутреннему ID)
    cursor.execute("""
        SELECT uc.coupon_code, p.description, s.name, s.address, uc.created_at, p.valid_days
        FROM user_coupons uc
        JOIN promotions p ON uc.promotion_id = p.id
        JOIN stores s ON p.store_id = s.id
        WHERE uc.user_id = ? AND uc.redeemed = 0
        ORDER BY uc.created_at DESC
    """, (user_id,))
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
        valid_until = created_at + timedelta(days=valid_days)
        await update.message.reply_text(
            f"🎁 {description}\n"
            f"🏪 \"Фасоль\", {store_address}\n"
            f"🔢 Код: <b>{coupon_code}</b>\n"
            f"📅 Дата получения: {created_at.strftime('%d.%m.%Y')}\n"
            f"⏳ Купон можно погасить до: {valid_until.strftime('%d.%m.%Y')}",
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
            [KeyboardButton("🔙 Выйти из админки")]
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

# ИСПРАВЛЕНО: Функция для показа статистики магазина, доступна как мастер-админу, так и админу магазина
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

# main.py (фрагмент)

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
        promotions = get_promotions(store_id)
        store = get_store(store_id)
        title = f"🎁 <b>Акции магазина {store['name']}</b>"
    else:
        store_id = admin[4] if len(admin) > 4 else None
        promotions = get_promotions(store_id)
        store = get_store(store_id)
        title = f"🎁 <b>Акции магазина {store['name']}</b>"
    
    if not promotions:
        await update.message.reply_text("📝 Акций пока нет")
        if role == "master" and user_id in MASTER_ADMIN_SELECTED_STORE:
            await show_selected_store_menu(update, context, store_id)
        return

    # ✅ Инициализируем ДО цикла и после return
    promo_text = f"{title}\n"

    for promo in promotions:
        # Распаковка: 8 полей
        promo_id, store_id_promo, description, start_date, duration, max_coupons, valid_days, created_at = promo
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

        # 🔹 Получаем количество выданных купонов по этой акции
        conn = sqlite3.connect('fasoley_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_coupons WHERE promotion_id = ?", (promo_id,))
        issued_coupons = cursor.fetchone()[0]
        conn.close()

        # 🔹 Формируем строку лимита
        if max_coupons > 0:
            limit_info = f"{issued_coupons} из {max_coupons}"
        else:
            limit_info = f"{issued_coupons} (без лимита)"

        promo_text += (
            f"ID: {promo_id}\n"
            f"🎁 Описание: {description}\n"
            f"📅 Период акции: {start_dt.strftime('%d.%m.%Y')} – {end_dt.strftime('%d.%m.%Y')}\n"
            f"📊 Выдано купонов: {limit_info}\n"
            f"⏳ Срок действия купона: {valid_days} дн.\n"
            f"📊 Статус: {status}\n"
            "━━━━━━━━━━━━━━━━\n"
        )

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
        "Шаг 1 из 5: Введите описание акции\n"
        "Например: 🍫 Шоколадка Snickers в подарок",
        reply_markup=reply_markup
    )
    USER_STATES[user_id] = "adding_promotion_description"

async def delete_promotion_start_for_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления акции мастер-админом из выбранного магазина"""
    user_id = update.effective_user.id
    if user_id not in ADMIN_SESSIONS or ADMIN_SESSIONS[user_id][3] != "master":
        await update.message.reply_text("❌ Доступ запрещен.")
        return
        
    if user_id not in MASTER_ADMIN_SELECTED_STORE:
        await update.message.reply_text("❌ Магазин не выбран.")
        return
        
    store_id = MASTER_ADMIN_SELECTED_STORE[user_id]
    promotions = get_promotions(store_id)

    if not promotions:
        await update.message.reply_text("❌ Нет акций для удаления")
        return

    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    promo_text = "❌ УДАЛЕНИЕ АКЦИИ\n\nВведите ID акции для удаления:\n\n"
    for promo in promotions:
        # ОБНОВЛЕННАЯ РАСПАКОВКА: 8 полей вместо 6
        promo_id, store_id_promo, description, start_date, duration, max_coupons, valid_days, created_at = promo
        promo_text += f"ID: {promo_id} - {description}\n"
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
        "Шаг 1 из 5: Введите описание акции\n"
        "Например: 🍫 Шоколадка Snickers в подарок",
        reply_markup=reply_markup
    )
    USER_STATES[user_id] = "adding_promotion_description"

async def delete_promotion_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало удаления акции (для админа магазина)"""
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
    promotions = get_promotions(store_id)

    if not promotions:
        await update.message.reply_text("❌ Нет акций для удаления")
        return

    keyboard = [[KeyboardButton("🔙 Назад")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    promo_text = "❌ УДАЛЕНИЕ АКЦИИ\n\nВведите ID акции для удаления:\n\n"
    for promo in promotions:
        # ОБНОВЛЕННАЯ РАСПАКОВКА: 8 полей вместо 6
        promo_id, store_id_promo, description, start_date, duration, max_coupons, valid_days, created_at = promo
        promo_text += f"ID: {promo_id} - {description}\n"
    await update.message.reply_text(promo_text, reply_markup=reply_markup)
    USER_STATES[user_id] = "deleting_promotion"

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
                elif state in ["adding_promotion_description", "adding_promotion_date", "adding_promotion_duration"]:
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
                            f"⏰ Время погашения: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
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
                "📅 Шаг 2 из 5: Введите дату начала акции\n"
                "Формат: ДД.ММ.ГГГГ\n"
                "Например: 22.08.2025", # Обновлено
                reply_markup=reply_markup
            )
            USER_STATES[user_id] = "adding_promotion_date"
        elif state == "adding_promotion_date":
            try:
              # Проверяем новый формат ДД-ММ-ГГГГ
                datetime.strptime(text, '%d.%m.%Y')
                context.user_data['promo_start_date'] = text
                keyboard = [[KeyboardButton("🔙 Назад")]]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                await update.message.reply_text(
                    "⏰ Шаг 3 из 5: Введите продолжительность акции в днях\n"
                    "Например: 7", # Обновлено
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
                    "📊 Шаг 4 из 5: Введите максимальное количество купонов по этой акции\n"
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
                    "⏰ Шаг 5 из 5: Введите количество дней, в течение которых купон будет действителен после получения\n"
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

                # Получаем все собранные данные
                admin = ADMIN_SESSIONS[user_id]
                role = admin[3]
                description = context.user_data['promo_description']
                start_date = context.user_data['promo_start_date']
                duration = context.user_data['promo_duration']
                max_coupons = context.user_data['promo_max_coupons']

                if role == "master":
                    if user_id not in MASTER_ADMIN_SELECTED_STORE:
                        await update.message.reply_text("❌ Ошибка: магазин не выбран.")
                        del USER_STATES[user_id]
                        return
                    store_id = MASTER_ADMIN_SELECTED_STORE[user_id]
                else:
                    store_id = admin[4] if len(admin) > 4 else None

                # СОЗДАЕМ акцию с ВСЕМИ параметрами
                create_promotion(store_id, description, start_date, duration, max_coupons, valid_days)
                store = get_store(store_id)
                success_msg = (f"✅ Акция успешно создана!\n\n"
                               f"🏪 Магазин: {store['name']}\n"
                               f"🎁 Акция: {description}\n"
                               f"📅 Длительность акции: {duration} дн.\n"
                               f"📊 Макс. купонов: {max_coupons if max_coupons > 0 else '∞'}\n"
                               f"⏳ Срок действия купона: {valid_days} дн.")
                del USER_STATES[user_id]
                if role == "master":
                    await show_selected_store_menu(update, context, store_id)
                else:
                    await update.message.reply_text(success_msg)
            except ValueError:
                await update.message.reply_text("❌ Введите число (количество дней, больше 0)")
        elif state == "deleting_promotion":
            try:
                promo_id = int(text)
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

                conn = sqlite3.connect('fasoley_bot.db')
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM promotions WHERE id = ? AND store_id = ?", (promo_id, store_id))
                promo = cursor.fetchone()
                if not promo:
                    await update.message.reply_text("❌ Акция не найдена или у вас нет прав на её удаление")
                    conn.close()
                    return
                cursor.execute("DELETE FROM promotions WHERE id = ?", (promo_id,))
                conn.commit()
                conn.close()
                success_msg = f"✅ Акция ID:{promo_id} успешно удалена!"
                del USER_STATES[user_id]
                # Возвращаем в соответствующее меню
                if role == "master":
                    await show_selected_store_menu(update, context, store_id)
                else:
                    # Для store-admin просто отправляем сообщение об успехе, НЕ показываем всю панель
                    await update.message.reply_text(success_msg)
            except ValueError:
                await update.message.reply_text("❌ Введите корректный ID акции")
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
            elif text == "📊 Статистика по магазинам":  # ← ДОБАВЬТЕ ЭТУ СТРОКУ
                await show_store_stats_list(update, context)  # ← ДОБАВЬТЕ ЭТУ СТРОКУ
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
        else: # store admin
            if text == "📊 Статистика магазина":
                await show_store_stats_for_master(update, context) # Используем исправленную функцию
            elif text == "🎁 Мои акции":
                await show_my_promotions(update, context)
            elif text == "➕ Добавить акцию":
                await add_promotion_start(update, context)
            elif text == "❌ Удалить акцию":
                await delete_promotion_start(update, context)


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