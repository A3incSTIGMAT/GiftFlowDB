import sqlite3
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from config import DB_PATH, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)

# Значения по умолчанию для цели
DEFAULT_GOAL_NAME = "На мечту"
DEFAULT_GOAL_AMOUNT = 150000

# ============ ПОДКЛЮЧЕНИЕ К БД ============

def get_db_connection():
    """Получить соединение с БД (синхронное)"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Инициализация базы данных: создание всех таблиц"""
    db_dir = Path(DB_PATH).parent
    if db_dir and not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Создана папка для БД: {db_dir}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP
        )
    """)
    
    # Таблица подарков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price INTEGER NOT NULL,
            icon TEXT DEFAULT '🎁',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица заказов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_id INTEGER NOT NULL,
            gift_name TEXT,
            amount INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            username TEXT,
            payment_method TEXT,
            payment_details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP,
            confirmed_by INTEGER
        )
    """)
    
    # Таблица транзакций
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id INTEGER,
            gift_id INTEGER,
            gift_name TEXT,
            amount INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            payment_method TEXT,
            payment_details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TIMESTAMP,
            confirmed_by INTEGER
        )
    """)
    
    # Таблица топа героев
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS top_heroes (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            total_amount INTEGER DEFAULT 0,
            last_donate TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица галереи
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            description TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица админов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            added_by INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица логов админов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Таблица настроек
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            goal_name TEXT NOT NULL,
            goal_amount INTEGER NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Индексы
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_top_heroes_amount ON top_heroes(total_amount DESC)")
    
    conn.commit()
    
    # Добавляем начальные подарки
    init_default_gifts()
    
    # Инициализируем настройки
    init_settings()
    
    conn.close()
    logger.info("✅ База данных инициализирована")

def init_settings():
    """Инициализация таблицы настроек с дефолтными значениями"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM settings WHERE id = 1")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute("""
            INSERT INTO settings (id, goal_name, goal_amount)
            VALUES (1, ?, ?)
        """, (DEFAULT_GOAL_NAME, DEFAULT_GOAL_AMOUNT))
        conn.commit()
    conn.close()

def init_default_gifts():
    """Добавление подарков, если таблица пуста"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM gifts")
    count = cursor.fetchone()[0]
    
    if count == 0:
        default_gifts = [
            ("🍬 Конфетка", "Маленькая сладость для Ланы", 10, "🍬"),
            ("🍫 Шоколадка", "Вкусный шоколад для поднятия настроения", 50, "🍫"),
            ("☕ Кофе", "Чашечка ароматного кофе", 100, "☕"),
            ("🐱 Корм Марсику", "Вкусняшка для любимого кота Ланы", 150, "🐱"),
            ("🍕 Пицца", "Лана закажет пиццу на стриме", 300, "🍕"),
            ("🎂 Тортик", "Сладкий подарок ко дню рождения", 500, "🎂"),
            ("🎮 Игра в Steam", "Лана купит игру по твоему желанию", 1000, "🎮"),
            ("📚 Книга", "Интересная книга для чтения", 1500, "📚"),
            ("🎫 Билет в кино", "Лана сходит в кино", 2000, "🎫"),
            ("💄 Косметика", "Красивый подарок для красоты", 5000, "💄"),
            ("👕 Футболка", "Брендовая футболка с принтом", 7500, "👕"),
            ("🎧 Наушники", "Качественные беспроводные наушники", 15000, "🎧"),
            ("⌚ Умные часы", "Стильные смарт-часы", 30000, "⌚"),
            ("📱 Новый телефон", "Современный смартфон", 75000, "📱"),
            ("💫 На мечту", "Поддержка большой мечты Ланы", 150000, "💫"),
        ]
        
        for name, desc, price, icon in default_gifts:
            cursor.execute("""
                INSERT INTO gifts (name, description, price, icon)
                VALUES (?, ?, ?, ?)
            """, (name, desc, price, icon))
        
        conn.commit()
        logger.info(f"✅ Добавлено {len(default_gifts)} подарков в базу")
    
    conn.close()

# ============ ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ============

def register_user_sync(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Регистрация или обновление пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_active)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()

# ============ ФУНКЦИИ ДЛЯ ПОДАРКОВ ============

def get_all_gifts_sync(active_only: bool = True) -> List[Dict]:
    """Получить все подарки"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if active_only:
        cursor.execute("SELECT * FROM gifts WHERE is_active = 1 ORDER BY price")
    else:
        cursor.execute("SELECT * FROM gifts ORDER BY price")
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_gift_by_id_sync(gift_id: int) -> Optional[Dict]:
    """Получить подарок по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gifts WHERE id = ?", (gift_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_gift_sync(name: str, price: int, description: str = "", icon: str = "🎁") -> int:
    """Добавить новый подарок"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO gifts (name, description, price, icon)
        VALUES (?, ?, ?, ?)
    """, (name, description, price, icon))
    conn.commit()
    gift_id = cursor.lastrowid
    conn.close()
    return gift_id

# ============ ФУНКЦИИ ДЛЯ ЗАКАЗОВ ============

def create_order_sync(user_id: int, gift_id: int, amount: int, username: str = None) -> int:
    """Создать новый заказ"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    gift = get_gift_by_id_sync(gift_id)
    gift_name = gift['name'] if gift else f"Подарок #{gift_id}"
    
    cursor.execute("""
        INSERT INTO orders (user_id, gift_id, gift_name, amount, status, username, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
    """, (user_id, gift_id, gift_name, amount, username))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id

def get_pending_orders_sync() -> List[Dict]:
    """Получить все заказы со статусом pending"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.*, u.username as user_username, u.first_name
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.status = 'pending'
        ORDER BY o.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def confirm_order_sync(order_id: int) -> bool:
    """Подтвердить заказ"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orders 
        SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (order_id,))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    
    if updated:
        conn2 = get_db_connection()
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT user_id, amount, username FROM orders WHERE id = ?", (order_id,))
        order = cursor2.fetchone()
        conn2.close()
        if order:
            update_top_heroes_sync(order['user_id'], order['amount'], order['username'])
    
    return updated

# ============ ФУНКЦИИ ДЛЯ ТРАНЗАКЦИЙ ============

def add_transaction_sync(user_id: int, gift_id: int, amount: int, payment_method: str = None) -> int:
    """Добавить новую транзакцию"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    gift = get_gift_by_id_sync(gift_id)
    gift_name = gift['name'] if gift else f"Подарок #{gift_id}"
    
    cursor.execute("""
        INSERT INTO transactions (user_id, gift_id, gift_name, amount, status, payment_method, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
    """, (user_id, gift_id, gift_name, amount, payment_method))
    conn.commit()
    transaction_id = cursor.lastrowid
    conn.close()
    return transaction_id

def update_transaction_status_sync(transaction_id: int, status: str, confirmed_by: int = None) -> bool:
    """Обновить статус транзакции"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE transactions 
        SET status = ?, confirmed_at = CURRENT_TIMESTAMP, confirmed_by = ?
        WHERE id = ?
    """, (status, confirmed_by, transaction_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    
    if updated and status == 'paid':
        conn2 = get_db_connection()
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT user_id, amount, username FROM transactions WHERE id = ?", (transaction_id,))
        transaction = cursor2.fetchone()
        conn2.close()
        if transaction:
            update_top_heroes_sync(transaction['user_id'], transaction['amount'], transaction['username'])
    
    return updated

def get_pending_transactions_sync(limit: int = 50) -> List[Dict]:
    """Получить ожидающие подтверждения транзакции"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, u.username, u.first_name
        FROM transactions t
        LEFT JOIN users u ON t.user_id = u.user_id
        WHERE t.status = 'pending'
        ORDER BY t.created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_transactions_sync(limit: int = 100) -> List[Dict]:
    """Получить все транзакции (для админа)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, u.username, u.first_name
        FROM transactions t
        LEFT JOIN users u ON t.user_id = u.user_id
        ORDER BY t.created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============ ФУНКЦИИ ДЛЯ ТОПА ГЕРОЕВ ============

def update_top_heroes_sync(user_id: int, amount: int, username: str = None):
    """Обновить топ героев после доната"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT total_amount FROM top_heroes WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if row:
        new_total = row[0] + amount
        cursor.execute("""
            UPDATE top_heroes 
            SET total_amount = ?, last_donate = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP, username = COALESCE(?, username)
            WHERE user_id = ?
        """, (new_total, username, user_id))
    else:
        cursor.execute("""
            INSERT INTO top_heroes (user_id, username, total_amount, last_donate)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (user_id, username, amount))
    
    conn.commit()
    conn.close()

def get_top_heroes_sync(limit: int = 10) -> List[Dict]:
    """Получить топ героев"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, total_amount, last_donate
        FROM top_heroes 
        ORDER BY total_amount DESC 
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============ ФУНКЦИИ ДЛЯ ГАЛЕРЕИ ============

def add_gallery_photo_sync(file_id: str, description: str = "", added_by: int = None) -> int:
    """Добавить фото в галерею"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO gallery (file_id, description, added_by)
        VALUES (?, ?, ?)
    """, (file_id, description, added_by))
    conn.commit()
    photo_id = cursor.lastrowid
    conn.close()
    return photo_id

def get_gallery_photos_sync(limit: int = 50) -> List[Dict]:
    """Получить фото из галереи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, file_id, description, added_by, added_at
        FROM gallery
        ORDER BY added_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_gallery_photo_sync(photo_id: int) -> bool:
    """Удалить фото из галереи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gallery WHERE id = ?", (photo_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

# ============ АДМИН ФУНКЦИИ ============

def is_admin_sync(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    if user_id == SUPER_ADMIN_ID or user_id == SUPPORT_ADMIN_ID:
        return True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def is_super_admin_sync(user_id: int) -> bool:
    """Проверка, является ли пользователь супер-админом"""
    return user_id == SUPER_ADMIN_ID

# ============ ФУНКЦИИ ДЛЯ СТАТИСТИКИ ============

def get_statistics_sync() -> Dict:
    """Получить статистику"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'confirmed'")
    total_orders = cursor.fetchone()[0]
    
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'confirmed'")
    total_amount = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    total_pending = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_users": total_users,
        "total_orders": total_orders,
        "total_amount": total_amount,
        "total_pending": total_pending,
        "total_donations": total_orders,
        "month_amount": total_amount
    }

def get_stats_sync() -> Dict:
    """Алиас для get_statistics_sync"""
    return get_statistics_sync()

# ============ ФУНКЦИИ ДЛЯ ЦЕЛИ ============

def get_goal_progress_sync() -> dict:
    """Получить прогресс цели"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT goal_name, goal_amount FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    goal_name = row[0] if row else DEFAULT_GOAL_NAME
    goal_amount = row[1] if row else DEFAULT_GOAL_AMOUNT
    
    collected = get_statistics_sync()['total_amount']
    
    if goal_amount > 0:
        percent = int(collected / goal_amount * 100)
        if percent > 100:
            percent = 100
    else:
        percent = 0
    
    bars_count = percent // 5
    bars = "█" * bars_count + "░" * (20 - bars_count)
    
    return {
        "name": goal_name,
        "target": goal_amount,
        "collected": collected,
        "percent": percent,
        "bars": bars,
        "remaining": goal_amount - collected if collected < goal_amount else 0
    }

# ============ АСИНХРОННЫЕ ОБЁРТКИ (ДЛЯ ОСНОВНОГО КОДА) ============

async def init_db():
    init_database()

async def get_all_gifts(active_only: bool = True):
    return get_all_gifts_sync(active_only)

async def get_gift_by_id(gift_id: int):
    return get_gift_by_id_sync(gift_id)

async def create_order(user_id: int, gift_id: int, amount: int, username: str = None):
    return create_order_sync(user_id, gift_id, amount, username)

async def add_transaction(user_id: int, gift_id: int, amount: int, payment_method: str = None):
    return add_transaction_sync(user_id, gift_id, amount, payment_method)

async def update_transaction_status(transaction_id: int, status: str, confirmed_by: int = None):
    return update_transaction_status_sync(transaction_id, status, confirmed_by)

async def get_pending_transactions(limit: int = 50):
    return get_pending_transactions_sync(limit)

async def get_all_transactions(limit: int = 100):
    return get_all_transactions_sync(limit)

async def update_stats_cache():
    return get_statistics_sync()

async def get_stats():
    return get_statistics_sync()

async def get_top_heroes(limit: int = 10):
    return get_top_heroes_sync(limit)

async def is_admin(user_id: int):
    return is_admin_sync(user_id)

async def is_super_admin(user_id: int):
    return is_super_admin_sync(user_id)

async def register_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    return register_user_sync(user_id, username, first_name, last_name)

async def get_goal_progress():
    return get_goal_progress_sync()

async def add_gallery_photo(file_id: str, description: str = "", added_by: int = None):
    return add_gallery_photo_sync(file_id, description, added_by)

async def get_gallery_photos(limit: int = 50):
    return get_gallery_photos_sync(limit)

async def delete_gallery_photo(photo_id: int):
    return delete_gallery_photo_sync(photo_id)

async def add_gift(name: str, price: int, description: str = "", icon: str = "🎁"):
    return add_gift_sync(name, price, description, icon)

# ============ ИНИЦИАЛИЗАЦИЯ ============

init_database()
