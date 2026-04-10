import sqlite3
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from config import DB_PATH, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)

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
    
    # Индексы
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_top_heroes_amount ON top_heroes(total_amount DESC)")
    
    conn.commit()
    
    # Добавляем начальные подарки
    init_default_gifts()
    
    conn.close()
    logger.info("✅ База данных инициализирована")

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

def register_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Регистрация или обновление пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_active)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (user_id, username, first_name, last_name))
    conn.commit()
    conn.close()

def get_user(user_id: int) -> Optional[Dict]:
    """Получить пользователя по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ============ ФУНКЦИИ ДЛЯ ПОДАРКОВ ============

def get_all_gifts(active_only: bool = True) -> List[Dict]:
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

def get_gift_by_id(gift_id: int) -> Optional[Dict]:
    """Получить подарок по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM gifts WHERE id = ?", (gift_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_gift(name: str, price: int, description: str = "", icon: str = "🎁") -> int:
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

def update_gift(gift_id: int, **kwargs):
    """Обновить информацию о подарке"""
    conn = get_db_connection()
    cursor = conn.cursor()
    fields = []
    values = []
    for key, value in kwargs.items():
        fields.append(f"{key} = ?")
        values.append(value)
    
    if fields:
        query = f"UPDATE gifts SET {', '.join(fields)} WHERE id = ?"
        values.append(gift_id)
        cursor.execute(query, values)
        conn.commit()
    conn.close()

def delete_gift(gift_id: int) -> bool:
    """Удалить подарок"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gifts WHERE id = ?", (gift_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

# ============ ФУНКЦИИ ДЛЯ ЗАКАЗОВ ============

def create_order(user_id: int, gift_id: int, amount: int, username: str = None) -> int:
    """Создать новый заказ"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    gift = get_gift_by_id(gift_id)
    gift_name = gift['name'] if gift else f"Подарок #{gift_id}"
    
    cursor.execute("""
        INSERT INTO orders (user_id, gift_id, gift_name, amount, status, username, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
    """, (user_id, gift_id, gift_name, amount, username))
    conn.commit()
    order_id = cursor.lastrowid
    conn.close()
    return order_id

def get_order(order_id: int) -> Optional[Dict]:
    """Получить заказ по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_pending_orders() -> List[Dict]:
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

def confirm_order(order_id: int) -> bool:
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
    
    # Обновляем топ героев
    if updated:
        order = get_order(order_id)
        if order:
            update_top_heroes(order['user_id'], order['amount'], order.get('username'))
    
    return updated

def reject_order(order_id: int) -> bool:
    """Отклонить заказ"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def update_order_status(order_id: int, status: str) -> bool:
    """Обновить статус заказа"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def get_user_orders(user_id: int, limit: int = 50) -> List[Dict]:
    """Получить заказы пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============ ФУНКЦИИ ДЛЯ ТРАНЗАКЦИЙ ============

def add_transaction(user_id: int, gift_id: int, amount: int, gift_name: str = None, payment_method: str = None) -> int:
    """Добавить новую транзакцию"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if not gift_name:
        gift = get_gift_by_id(gift_id)
        gift_name = gift['name'] if gift else f"Подарок #{gift_id}"
    
    cursor.execute("""
        INSERT INTO transactions (user_id, gift_id, gift_name, amount, status, payment_method, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
    """, (user_id, gift_id, gift_name, amount, payment_method))
    conn.commit()
    transaction_id = cursor.lastrowid
    conn.close()
    return transaction_id

def update_transaction_status(transaction_id: int, status: str, confirmed_by: int = None) -> bool:
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
    return updated

def get_pending_transactions(limit: int = 50) -> List[Dict]:
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

def get_all_transactions(limit: int = 100) -> List[Dict]:
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

def get_transaction_by_id(transaction_id: int) -> Optional[Dict]:
    """Получить транзакцию по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ============ ФУНКЦИИ ДЛЯ ТОПА ГЕРОЕВ ============

def update_top_heroes(user_id: int, amount: int, username: str = None):
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

def get_top_heroes(limit: int = 10) -> List[Dict]:
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

def get_user_rank(user_id: int) -> Optional[int]:
    """Получить место пользователя в топе"""
    heroes = get_top_heroes(limit=100)
    for i, hero in enumerate(heroes):
        if hero["user_id"] == user_id:
            return i + 1
    return None

# ============ ФУНКЦИИ ДЛЯ ГАЛЕРЕИ ============

def add_gallery_photo(file_id: str, description: str = "", added_by: int = None) -> int:
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

def get_gallery_photos(limit: int = 50) -> List[Dict]:
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

def delete_gallery_photo(photo_id: int) -> bool:
    """Удалить фото из галереи"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gallery WHERE id = ?", (photo_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

# ============ АДМИН ФУНКЦИИ ============

def is_super_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь супер-админом"""
    return user_id == SUPER_ADMIN_ID

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    if user_id == SUPER_ADMIN_ID or user_id == SUPPORT_ADMIN_ID:
        return True
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def add_admin(user_id: int, username: str = None, added_by: int = None) -> bool:
    """Добавить администратора"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO admins (user_id, username, added_by)
            VALUES (?, ?, ?)
        """, (user_id, username, added_by or SUPER_ADMIN_ID))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления админа: {e}")
        return False
    finally:
        conn.close()

def remove_admin(user_id: int) -> bool:
    """Удалить администратора"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted

def get_all_admins() -> List[Dict]:
    """Получить список всех администраторов"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, added_by, added_at 
        FROM admins 
        ORDER BY added_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============ ФУНКЦИИ ДЛЯ СТАТИСТИКИ ============

def get_statistics() -> Dict:
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
        "total_pending": total_pending
    }

# ============ ФУНКЦИИ ДЛЯ ЛОГОВ ============

def log_admin_action(admin_id: int, action: str, details: str = None):
    """Записать действие админа в лог"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO admin_logs (admin_id, action, details)
        VALUES (?, ?, ?)
    """, (admin_id, action, details))
    conn.commit()
    conn.close()

# ============ ИНИЦИАЛИЗАЦИЯ ============

# Создаём таблицы при импорте модуля
init_database()
