# database.py
import sqlite3
import hashlib
import random
import string
from datetime import datetime, timedelta

def get_db_connection():
    conn = sqlite3.connect('fasoley_bot.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    # Создание таблиц
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            store_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            address TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(city, address, name)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL, -- 'master' or 'store'
            store_id INTEGER,
            FOREIGN KEY (store_id) REFERENCES stores (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS promotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            start_date DATE NOT NULL,
            duration INTEGER NOT NULL,
            max_coupons INTEGER DEFAULT 0,  -- Макс. количество купонов (0 = без лимита)
            valid_days INTEGER DEFAULT 1,   -- Дней на погашение после получения
            starts_today BOOLEAN DEFAULT 1, -- НОВОЕ: Стартует ли акция день в день (1) или на следующий день (0)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (store_id) REFERENCES stores (id)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            promotion_id INTEGER NOT NULL,
            coupon_code TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            redeemed BOOLEAN DEFAULT 0,
            redeemed_at TIMESTAMP NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (promotion_id) REFERENCES promotions (id)
        )
    ''')

    conn.commit()

    # Добавление тестовых данных
    cursor = conn.cursor()

    # Магазины - используем INSERT OR IGNORE с проверкой по всем полям
    stores_data = [
        ("Москва", "ул. Тверская, 1", "Фасоль Москва-1"),
        ("Москва", "ул. Арбат, 10", "Фасоль Москва-2"),
        ("Самара", "ул. Ленина, 25", "Фасоль Самара-1"),
        ("Ростов-на-Дону", "пл. Гагарина, 5", "Фасоль Ростов-1")
    ]
    
    for store in stores_data:
        cursor.execute("""
            INSERT OR IGNORE INTO stores (city, address, name) 
            VALUES (?, ?, ?)
        """, store)

    # Администраторы
    admins_data = [
        ("master", hashlib.sha256("master".encode()).hexdigest(), "master", None),
        ("m1", hashlib.sha256("m1".encode()).hexdigest(), "store", 1),
        ("m2", hashlib.sha256("m2".encode()).hexdigest(), "store", 2),
        ("s1", hashlib.sha256("s1".encode()).hexdigest(), "store", 3),
        ("r1", hashlib.sha256("r1".encode()).hexdigest(), "store", 4),
    ]
    
    for admin in admins_data:
        cursor.execute("""
            INSERT OR IGNORE INTO admins (login, password_hash, role, store_id) 
            VALUES (?, ?, ?, ?)
        """, admin)

    # Проверяем, есть ли уже акции, чтобы не дублировать при повторном запуске
    cursor.execute("SELECT COUNT(*) FROM promotions")
    promo_count = cursor.fetchone()[0]
    
    if promo_count == 0: # Добавляем акции только если их еще нет
        # Акции (по 3 для каждого магазина) - с новым полем starts_today
        promotions_data = []
        for store_id in range(1, 5):
            promotions_data.extend([
                (store_id, "☕ Кофе в подарок", "24.10.2025", 30, 100, 3, 1),  # 100 купонов, 3 дня на погашение, старт день в день
                (store_id, "📉 Скидка 5% на чек", "24.10.2025", 30, 0, 1, 0),   # Без лимита, 1 день, старт на следующий день
                (store_id, "🍭 Конфеты в подарок", "24.10.2025", 30, 50, 7, 1), # 50 купонов, 7 дней, старт день в день
            ])
        
        for promo in promotions_data:
            # Преобразуем ДД.ММ.ГГГГ в ГГГГ-ММ-ДД для хранения в БД
            try:
                date_obj = datetime.strptime(promo[2], '%d.%m.%Y')
                db_date = date_obj.strftime('%Y-%m-%d')
                # НОВЫЙ запрос с новыми полями
                cursor.execute("""
                    INSERT OR IGNORE INTO promotions (store_id, description, start_date, duration, max_coupons, valid_days, starts_today) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (promo[0], promo[1], db_date, promo[3], promo[4], promo[5], promo[6]))
            except ValueError:
                # Если не удалось распарсить, вставляем как есть
                cursor.execute("""
                    INSERT OR IGNORE INTO promotions (store_id, description, start_date, duration, max_coupons, valid_days, starts_today) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, promo)

    conn.commit()
    conn.close()

# Функции доступа к данным
def get_user(telegram_id):
    conn = get_db_connection()
    user = conn.execute("SELECT store_id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    conn.close()
    return user['store_id'] if user else None

def create_user(telegram_id, store_id):
    conn = get_db_connection()
    
    # Проверяем, не существует ли уже пользователь
    existing_user = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    
    if existing_user:
        # Если пользователь существует, обновляем store_id
        conn.execute("UPDATE users SET store_id = ? WHERE telegram_id = ?", (store_id, telegram_id))
    else:
        # Если пользователя нет, создаем нового
        conn.execute("INSERT INTO users (telegram_id, store_id) VALUES (?, ?)", (telegram_id, store_id))
    
    conn.commit()
    conn.close()

def get_stores():
    conn = get_db_connection()
    stores = conn.execute("SELECT id, city, address, name FROM stores").fetchall()
    conn.close()
    return [dict(store) for store in stores]

def get_store(store_id):
    conn = get_db_connection()
    store = conn.execute("SELECT id, city, address, name FROM stores WHERE id = ?", (store_id,)).fetchone()
    conn.close()
    return dict(store) if store else None

def get_promotions(store_id=None):
    conn = get_db_connection()
    if store_id:
        rows = conn.execute("SELECT * FROM promotions WHERE store_id = ?", (store_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM promotions").fetchall()
    conn.close()
    return [tuple(row) for row in rows]

def get_promotions_with_local_ids(store_id=None):
    """Получить акции с локальными ID для каждого магазина"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row  # ДОБАВЛЕНО: устанавливаем row_factory для доступа по ключам
    
    if store_id:
        # Для конкретного магазина - локальная нумерация с 1
        query = """
            SELECT p.*, 
                   (ROW_NUMBER() OVER (PARTITION BY p.store_id ORDER BY p.id)) as local_id
            FROM promotions p
            WHERE p.store_id = ?
            ORDER BY p.id
        """
        rows = conn.execute(query, (store_id,)).fetchall()
    else:
        # Для всех магазинов - локальная нумерация в контексте каждого магазина
        query = """
            SELECT p.*, 
                   (ROW_NUMBER() OVER (PARTITION BY p.store_id ORDER BY p.id)) as local_id
            FROM promotions p
            ORDER BY p.store_id, p.id
        """
        rows = conn.execute(query).fetchall()
    
    conn.close()
    return [dict(row) for row in rows]  

def create_promotion(store_id, description, start_date, duration, max_coupons=0, valid_days=1, starts_today=1):
    # Преобразуем ДД.ММ.ГГГГ в ГГГГ-ММ-ДД для хранения в БД
    try:
        date_obj = datetime.strptime(start_date, '%d.%m.%Y')
        db_date = date_obj.strftime('%Y-%m-%d')
    except ValueError:
        db_date = start_date
    
    conn = get_db_connection()
    # НОВЫЙ запрос на вставку с полем starts_today
    conn.execute("""
        INSERT INTO promotions (store_id, description, start_date, duration, max_coupons, valid_days, starts_today) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (store_id, description, db_date, duration, max_coupons, valid_days, starts_today))
    conn.commit()
    conn.close()
    
def get_user_coupon(telegram_id, date):
    """Получить купон пользователя за определенную дату"""
    conn = get_db_connection()
    
    # Сначала находим правильный user_id
    user_row = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
    
    if not user_row:
        conn.close()
        return None
        
    correct_user_id = user_row['id']
    
    coupon = conn.execute("""
        SELECT * FROM user_coupons 
        WHERE user_id = ? AND DATE(created_at) = ? AND redeemed = 0
    """, (correct_user_id, date)).fetchone()
    conn.close()
    return dict(coupon) if coupon else None

def create_coupon(user_id, promotion):
    conn = get_db_connection()
    promo_id = promotion[0]
    
    # Находим правильный user_id (id из таблицы users) для данного telegram_id
    user_row = conn.execute("SELECT id FROM users WHERE telegram_id = ?", (user_id,)).fetchone()
    if not user_row:
        conn.close()
        raise ValueError(f"Пользователь с telegram_id {user_id} не найден")
    
    correct_user_id = user_row['id']
    
    # Генерируем уникальный 6-значный код
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        exists = conn.execute("SELECT 1 FROM user_coupons WHERE coupon_code = ?", (code,)).fetchone()
        if not exists:
            break
    
    # Используем правильный user_id (id из таблицы users)
    conn.execute("""
        INSERT INTO user_coupons (user_id, promotion_id, coupon_code) 
        VALUES (?, ?, ?)
    """, (correct_user_id, promo_id, code))
    
    conn.commit()
    conn.close()
    return code

def redeem_coupon_by_code(code, user_id):
    conn = get_db_connection()
    
    print(f"🔍 Поиск купона: {code}")
    print(f"🔍 User ID: {user_id}")
    
    # Полный запрос с правильными JOIN'ами
    coupon = conn.execute("""
    SELECT 
        uc.*, 
        p.description, 
        p.store_id,
        p.valid_days,
        p.starts_today,        -- ← ДОБАВЛЕНО
        s.name, 
        s.address, 
        s.city, 
        u.telegram_id
    FROM user_coupons uc
    JOIN promotions p ON uc.promotion_id = p.id
    JOIN stores s ON p.store_id = s.id
    JOIN users u ON uc.user_id = u.id  
    WHERE uc.coupon_code = ? AND uc.redeemed = 0
""", (code,)).fetchone()

    print(f"🔍 Полный запрос результат: {coupon}")
    
    if not coupon:
        conn.close()
        print(f"❌ Купон {code} не найден полным запросом")
        return {"status": "not_found"}

    # Проверяем дату
    created_date = datetime.strptime(coupon['created_at'], '%Y-%m-%d %H:%M:%S').date()
    valid_days = coupon['valid_days'] # Получаем valid_days из акции
    expiry_date = created_date + timedelta(days=valid_days)
    today = datetime.now().date()
    
    if today > expiry_date:
        conn.close()
        return {"status": "expired"}

    # Погашаем
    conn.execute("""
        UPDATE user_coupons 
        SET redeemed = 1, redeemed_at = CURRENT_TIMESTAMP 
        WHERE coupon_code = ?
    """, (code,))
    conn.commit()
    
    # Формируем данные для возврата
    result_data = {
        "status": "success",
        "description": coupon['description'],
        "store_name": coupon['name'],
        "address": coupon['address'],
        "city": coupon['city'],
        "code": code,
        "owner_telegram_id": coupon['telegram_id']
    }
    
    print(f"✅ Купон {code} успешно погашен")
    conn.close()
    return result_data
    
def get_admin(login, password):
    conn = get_db_connection()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    admin = conn.execute("SELECT * FROM admins WHERE login = ? AND password_hash = ?", (login, password_hash)).fetchone()
    conn.close()
    # Возвращаем кортеж для совместимости с предыдущим кодом
    return tuple(admin) if admin else None

def create_store(city, address, name):
    """Создание нового магазина"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем, нет ли уже магазина с такими данными
    cursor.execute("""
        SELECT id FROM stores 
        WHERE city = ? AND address = ? AND name = ?
    """, (city, address, name))
    
    existing_store = cursor.fetchone()
    if existing_store:
        conn.close()
        return None  # Магазин уже существует
    
    # Создаем новый магазин
    cursor.execute("""
        INSERT INTO stores (city, address, name) 
        VALUES (?, ?, ?)
    """, (city, address, name))
    
    store_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return store_id

def create_store_admin(login, password, store_id):
    """Создание администратора для магазина"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Проверяем, нет ли уже администратора с таким логином
    cursor.execute("SELECT id FROM admins WHERE login = ?", (login,))
    existing_admin = cursor.fetchone()
    if existing_admin:
        conn.close()
        return False  # Логин уже занят
    
    # Создаем администратора магазина
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("""
        INSERT INTO admins (login, password_hash, role, store_id) 
        VALUES (?, ?, 'store', ?)
    """, (login, password_hash, store_id))
    
    conn.commit()
    conn.close()
    return True

def delete_store(store_id):
    """Удаление магазина и связанных данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Удаляем связанные записи в правильном порядке
        cursor.execute("DELETE FROM user_coupons WHERE promotion_id IN (SELECT id FROM promotions WHERE store_id = ?)", (store_id,))
        cursor.execute("DELETE FROM promotions WHERE store_id = ?", (store_id,))
        cursor.execute("DELETE FROM admins WHERE store_id = ?", (store_id,))
        cursor.execute("UPDATE users SET store_id = NULL WHERE store_id = ?", (store_id,))
        cursor.execute("DELETE FROM stores WHERE id = ?", (store_id,))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"Ошибка при удалении магазина: {e}")
        return False

def get_promotion_with_start_type(promotion_id):
    """Получить информацию об акции с типом старта"""
    conn = get_db_connection()
    promotion = conn.execute("SELECT * FROM promotions WHERE id = ?", (promotion_id,)).fetchone()
    conn.close()
    return dict(promotion) if promotion else None



