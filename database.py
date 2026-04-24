import sqlite3
import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import contextmanager

from config import DB_PATH, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)

# Значения по умолчанию для цели
DEFAULT_GOAL_NAME = "На мечту"
DEFAULT_GOAL_AMOUNT = 150000

# ============ КОНТЕКСТНЫЙ МЕНЕДЖЕР ДЛЯ БД ============

@contextmanager
def get_db_cursor(commit: bool = True):
    """
    Контекстный менеджер для безопасной работы с БД.
    Автоматически делает commit/rollback и закрывает соединение.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"❌ SQLite error: {e}")
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Unexpected error: {e}")
        raise
    finally:
        conn.close()


# ============ ПОДКЛЮЧЕНИЕ К БД ============

def get_db_connection():
    """Получить соединение с БД с оптимальными настройками"""
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=10.0,
        check_same_thread=False,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    # Оптимизации для SQLite
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")  # 64MB кэш
    return conn


def init_database():
    """Инициализация базы данных: создание всех таблиц"""
    try:
        db_dir = Path(DB_PATH).parent
        if db_dir and not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Создана папка для БД: {db_dir}")
        
        with get_db_cursor() as cursor:
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
                    confirmed_by INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
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
                    confirmed_by INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS top_heroes (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    total_amount INTEGER DEFAULT 0,
                    last_donate TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gallery (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT NOT NULL,
                    description TEXT,
                    added_by INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (added_by) REFERENCES users(user_id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    added_by INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                    goal_name TEXT NOT NULL,
                    goal_amount INTEGER NOT NULL CHECK (goal_amount >= 0),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Индексы
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_top_heroes_amount ON top_heroes(total_amount DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_gallery_added ON gallery(added_at DESC)")
        
        init_default_gifts()
        init_settings()
        
        logger.info("✅ База данных инициализирована успешно")
        return True
        
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при инициализации БД: {e}")
        raise


def init_settings():
    """Инициализация таблицы настроек"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM settings WHERE id = 1")
            count = cursor.fetchone()[0]
            if count == 0:
                cursor.execute("""
                    INSERT INTO settings (id, goal_name, goal_amount)
                    VALUES (1, ?, ?)
                """, (DEFAULT_GOAL_NAME, DEFAULT_GOAL_AMOUNT))
                logger.info(f"✅ Настройки инициализированы: {DEFAULT_GOAL_NAME} ({DEFAULT_GOAL_AMOUNT})")
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка инициализации настроек: {e}")
        raise


def init_default_gifts():
    """Добавление подарков, если таблица пуста"""
    try:
        with get_db_cursor() as cursor:
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
                
                cursor.executemany("""
                    INSERT INTO gifts (name, description, price, icon)
                    VALUES (?, ?, ?, ?)
                """, default_gifts)
                
                logger.info(f"✅ Добавлено {len(default_gifts)} подарков в базу")
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка инициализации подарков: {e}")
        raise


# ============ ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ============

def register_user_sync(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Регистрация или обновление пользователя"""
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f"Некорректный user_id: {user_id}")
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_active)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, username, first_name, last_name))
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка регистрации пользователя {user_id}: {e}")
        raise


def get_user_sync(user_id: int) -> Optional[Dict]:
    """Получить данные пользователя по user_id"""
    if not isinstance(user_id, int) or user_id <= 0:
        return None
    
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения пользователя {user_id}: {e}")
        return None


# ============ ФУНКЦИИ ДЛЯ ПОДАРКОВ ============

def get_all_gifts_sync(active_only: bool = True) -> List[Dict]:
    """Получить все подарки"""
    try:
        with get_db_cursor(commit=False) as cursor:
            if active_only:
                cursor.execute("SELECT * FROM gifts WHERE is_active = 1 ORDER BY price")
            else:
                cursor.execute("SELECT * FROM gifts ORDER BY price")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения подарков: {e}")
        return []


def get_gift_by_id_sync(gift_id: int) -> Optional[Dict]:
    """Получить подарок по ID"""
    if not isinstance(gift_id, int) or gift_id <= 0:
        return None
    
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT * FROM gifts WHERE id = ?", (gift_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения подарка #{gift_id}: {e}")
        return None


def add_gift_sync(name: str, price: int, description: str = "", icon: str = "🎁", is_active: int = 1) -> int:
    """Добавить новый подарок"""
    if not name or not isinstance(price, int) or price <= 0:
        raise ValueError("Некорректные данные подарка")
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO gifts (name, description, price, icon, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (name, description, price, icon, is_active))
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка добавления подарка: {e}")
        raise


def update_gift_sync(gift_id: int, name: str = None, price: int = None, 
                     description: str = None, icon: str = None, is_active: int = None) -> bool:
    """Обновить данные подарка"""
    if not isinstance(gift_id, int) or gift_id <= 0:
        return False
    
    try:
        with get_db_cursor() as cursor:
            updates, params = [], []
            if name is not None: updates.append("name = ?"); params.append(name)
            if price is not None: updates.append("price = ?"); params.append(price)
            if description is not None: updates.append("description = ?"); params.append(description)
            if icon is not None: updates.append("icon = ?"); params.append(icon)
            if is_active is not None: updates.append("is_active = ?"); params.append(is_active)
            
            if not updates: return True
            
            params.append(gift_id)
            cursor.execute(f"UPDATE gifts SET {', '.join(updates)} WHERE id = ?", params)
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка обновления подарка #{gift_id}: {e}")
        return False


# ============ ФУНКЦИИ ДЛЯ ЗАКАЗОВ ============

def create_order_sync(user_id: int, gift_id: int, amount: int, username: str = None) -> int:
    """Создать новый заказ"""
    if not isinstance(user_id, int) or user_id <= 0: raise ValueError(f"Некорректный user_id: {user_id}")
    if not isinstance(gift_id, int) or gift_id <= 0: raise ValueError(f"Некорректный gift_id: {gift_id}")
    if not isinstance(amount, int) or amount <= 0: raise ValueError(f"Сумма должна быть > 0: {amount}")
    
    try:
        with get_db_cursor() as cursor:
            gift = get_gift_by_id_sync(gift_id)
            gift_name = gift['name'] if gift else f"Подарок #{gift_id}"
            
            cursor.execute("""
                INSERT INTO orders (user_id, gift_id, gift_name, amount, status, username, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
            """, (user_id, gift_id, gift_name, amount, username))
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка создания заказа: {e}")
        raise


def get_pending_orders_sync(limit: int = 100) -> List[Dict]:
    """Получить ожидающие заказы"""
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT o.*, u.username as user_username, u.first_name
                FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
                WHERE o.status = 'pending' ORDER BY o.created_at DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения ожидающих заказов: {e}")
        return []


def get_all_orders_sync(limit: int = 100) -> List[Dict]:
    """Получить все заказы"""
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT o.*, u.username as user_username, u.first_name
                FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
                ORDER BY o.created_at DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения заказов: {e}")
        return []


def get_order_by_id_sync(order_id: int) -> Optional[Dict]:
    """Получить заказ по ID"""
    if not isinstance(order_id, int) or order_id <= 0: return None
    
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT o.*, u.username as user_username, u.first_name
                FROM orders o LEFT JOIN users u ON o.user_id = u.user_id WHERE o.id = ?
            """, (order_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения заказа #{order_id}: {e}")
        return None


# Алиас для совместимости с admin.py
get_order_sync = get_order_by_id_sync


def confirm_order_sync(order_id: int, confirmed_by: int = None) -> bool:
    """Подтвердить заказ"""
    if not isinstance(order_id, int) or order_id <= 0: return False
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT o.user_id, o.amount, o.username, u.username as real_username
                FROM orders o LEFT JOIN users u ON o.user_id = u.user_id
                WHERE o.id = ? AND o.status = 'pending'
            """, (order_id,))
            order = cursor.fetchone()
            
            if not order: return False
            
            cursor.execute("""
                UPDATE orders SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP, confirmed_by = ?
                WHERE id = ?
            """, (confirmed_by, order_id))
            
            if cursor.rowcount > 0:
                update_top_heroes_sync(order['user_id'], order['amount'], order['real_username'] or order['username'])
                return True
            return False
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка подтверждения заказа #{order_id}: {e}")
        return False


def reject_order_sync(order_id: int, confirmed_by: int = None) -> bool:
    """Отклонить заказ"""
    if not isinstance(order_id, int) or order_id <= 0: return False
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT user_id FROM orders WHERE id = ? AND status = 'pending'
            """, (order_id,))
            order = cursor.fetchone()
            
            if not order: return False
            
            cursor.execute("""
                UPDATE orders SET status = 'rejected', confirmed_at = CURRENT_TIMESTAMP, confirmed_by = ?
                WHERE id = ?
            """, (confirmed_by, order_id))
            
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка отклонения заказа #{order_id}: {e}")
        return False


def cancel_order_sync(order_id: int) -> bool:
    """Отменить заказ"""
    if not isinstance(order_id, int) or order_id <= 0: return False
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("UPDATE orders SET status = 'cancelled' WHERE id = ? AND status = 'pending'", (order_id,))
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка отмены заказа #{order_id}: {e}")
        return False


# ============ ФУНКЦИИ ДЛЯ ТРАНЗАКЦИЙ ============

def add_transaction_sync(user_id: int, gift_id: int, amount: int, 
                         payment_method: str = None, order_id: int = None) -> int:
    """Добавить новую транзакцию"""
    if not isinstance(user_id, int) or user_id <= 0: raise ValueError(f"Некорректный user_id: {user_id}")
    if not isinstance(gift_id, int) or gift_id <= 0: raise ValueError(f"Некорректный gift_id: {gift_id}")
    if not isinstance(amount, int) or amount <= 0: raise ValueError(f"Сумма должна быть > 0: {amount}")
    
    try:
        with get_db_cursor() as cursor:
            gift = get_gift_by_id_sync(gift_id)
            gift_name = gift['name'] if gift else f"Подарок #{gift_id}"
            
            cursor.execute("""
                INSERT INTO transactions (user_id, gift_id, gift_name, amount, status, 
                                         payment_method, order_id, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, gift_id, gift_name, amount, payment_method, order_id))
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка создания транзакции: {e}")
        raise


def update_transaction_status_sync(transaction_id: int, status: str, confirmed_by: int = None) -> bool:
    """Обновить статус транзакции"""
    if not isinstance(transaction_id, int) or transaction_id <= 0: return False
    if status not in ('pending', 'paid', 'cancelled', 'refunded'):
        raise ValueError(f"Некорректный статус: {status}")
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT t.user_id, t.amount, u.username
                FROM transactions t LEFT JOIN users u ON t.user_id = u.user_id
                WHERE t.id = ? AND t.status = 'pending'
            """, (transaction_id,))
            transaction = cursor.fetchone()
            
            if not transaction: return False
            
            cursor.execute("""
                UPDATE transactions SET status = ?, confirmed_at = CURRENT_TIMESTAMP, confirmed_by = ?
                WHERE id = ?
            """, (status, confirmed_by, transaction_id))
            
            if cursor.rowcount > 0 and status == 'paid':
                update_top_heroes_sync(transaction['user_id'], transaction['amount'], transaction['username'])
            
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка обновления транзакции #{transaction_id}: {e}")
        return False


def get_pending_transactions_sync(limit: int = 50) -> List[Dict]:
    """Получить ожидающие транзакции"""
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT t.*, u.username, u.first_name
                FROM transactions t LEFT JOIN users u ON t.user_id = u.user_id
                WHERE t.status = 'pending' ORDER BY t.created_at DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения ожидающих транзакций: {e}")
        return []


def get_all_transactions_sync(limit: int = 100, status: str = None) -> List[Dict]:
    """Получить все транзакции"""
    try:
        with get_db_cursor(commit=False) as cursor:
            if status:
                cursor.execute("""
                    SELECT t.*, u.username, u.first_name
                    FROM transactions t LEFT JOIN users u ON t.user_id = u.user_id
                    WHERE t.status = ? ORDER BY t.created_at DESC LIMIT ?
                """, (status, limit))
            else:
                cursor.execute("""
                    SELECT t.*, u.username, u.first_name
                    FROM transactions t LEFT JOIN users u ON t.user_id = u.user_id
                    ORDER BY t.created_at DESC LIMIT ?
                """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения транзакций: {e}")
        return []


# ============ ФУНКЦИИ ДЛЯ ТОПА ГЕРОЕВ ============

def update_top_heroes_sync(user_id: int, amount: int, username: str = None):
    """Обновить топ героев"""
    if not isinstance(user_id, int) or user_id <= 0: return
    if not isinstance(amount, int) or amount <= 0: return
    
    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT total_amount FROM top_heroes WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                new_total = row[0] + amount
                cursor.execute("""
                    UPDATE top_heroes SET total_amount = ?, last_donate = CURRENT_TIMESTAMP, 
                        updated_at = CURRENT_TIMESTAMP, username = COALESCE(?, username)
                    WHERE user_id = ?
                """, (new_total, username, user_id))
            else:
                cursor.execute("""
                    INSERT INTO top_heroes (user_id, username, total_amount, last_donate)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, username, amount))
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка обновления топа героев: {e}")


def get_top_heroes_sync(limit: int = 10) -> List[Dict]:
    """Получить топ героев"""
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("""
                SELECT user_id, username, total_amount, last_donate
                FROM top_heroes WHERE total_amount > 0 ORDER BY total_amount DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения топа героев: {e}")
        return []


# ============ ФУНКЦИИ ДЛЯ ГАЛЕРЕИ ============

def add_gallery_photo_sync(file_id: str, description: str = "", added_by: int = None) -> int:
    """Добавить фото в галерею"""
    if not file_id: raise ValueError("file_id не может быть пустым")
    try:
        with get_db_cursor() as cursor:
            cursor.execute("INSERT INTO gallery (file_id, description, added_by) VALUES (?, ?, ?)", (file_id, description, added_by))
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка добавления фото: {e}")
        raise


def get_gallery_photos_sync(limit: int = 50) -> List[Dict]:
    """Получить фото из галереи"""
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT id, file_id, description, added_by, added_at FROM gallery ORDER BY added_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения галереи: {e}")
        return []


def delete_gallery_photo_sync(photo_id: int) -> bool:
    """Удалить фото из галереи"""
    if not isinstance(photo_id, int) or photo_id <= 0: return False
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM gallery WHERE id = ?", (photo_id,))
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка удаления фото #{photo_id}: {e}")
        return False


# ============ АДМИН ФУНКЦИИ ============

def is_admin_sync(user_id: int) -> bool:
    """Проверка админа"""
    if user_id in (SUPER_ADMIN_ID, SUPPORT_ADMIN_ID): return True
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
            return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка проверки админа {user_id}: {e}")
        return False


def is_super_admin_sync(user_id: int) -> bool:
    """Проверка супер-админа"""
    return user_id == SUPER_ADMIN_ID


def add_admin_sync(user_id: int, added_by: int = None) -> bool:
    """Добавить админа"""
    if not isinstance(user_id, int) or user_id <= 0: return False
    try:
        with get_db_cursor() as cursor:
            cursor.execute("INSERT OR IGNORE INTO admins (user_id, username, added_by) VALUES (?, ?, ?)", (user_id, None, added_by))
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка добавления админа {user_id}: {e}")
        return False


def remove_admin_sync(user_id: int) -> bool:
    """Удалить админа"""
    if user_id in (SUPER_ADMIN_ID, SUPPORT_ADMIN_ID): return False
    try:
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка удаления админа {user_id}: {e}")
        return False


def log_admin_action_sync(admin_id: int, action: str, details: str = None):
    """Записать действие админа"""
    if not isinstance(admin_id, int) or admin_id <= 0: return
    try:
        with get_db_cursor() as cursor:
            cursor.execute("INSERT INTO admin_logs (admin_id, action, details) VALUES (?, ?, ?)", (admin_id, action, details))
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка логирования действия админа: {e}")


# ============ ФУНКЦИИ ДЛЯ СТАТИСТИКИ И ЦЕЛИ ============

def get_statistics_sync() -> Dict[str, Any]:
    """Получить статистику"""
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'confirmed'")
            total_orders = cursor.fetchone()[0]
            
            cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'confirmed'")
            total_amount = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
            total_pending = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COALESCE(SUM(amount), 0) FROM orders 
                WHERE status = 'confirmed' AND created_at >= date('now', '-30 days')
            """)
            month_amount = cursor.fetchone()[0] or 0
            
            return {
                "total_users": total_users, "total_orders": total_orders, "total_amount": total_amount,
                "total_pending": total_pending, "total_donations": total_orders, "month_amount": month_amount
            }
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения статистики: {e}")
        return {"total_users": 0, "total_orders": 0, "total_amount": 0, "total_pending": 0, "total_donations": 0, "month_amount": 0}


def get_stats_sync() -> Dict[str, Any]:
    """Алиас для статистики"""
    return get_statistics_sync()


def update_stats_cache_sync() -> Dict[str, Any]:
    """Обновить кэш статистики"""
    return get_statistics_sync()


def get_goal_progress_sync() -> dict:
    """Получить прогресс цели"""
    try:
        with get_db_cursor(commit=False) as cursor:
            cursor.execute("SELECT goal_name, goal_amount FROM settings WHERE id = 1")
            row = cursor.fetchone()
            goal_name = row[0] if row and row[0] else DEFAULT_GOAL_NAME
            goal_amount = row[1] if row and row[1] else DEFAULT_GOAL_AMOUNT
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка получения настроек цели: {e}")
        goal_name, goal_amount = DEFAULT_GOAL_NAME, DEFAULT_GOAL_AMOUNT
    
    collected = get_statistics_sync()['total_amount']
    percent = min(int(collected / goal_amount * 100), 100) if goal_amount > 0 else 0
    bars = "█" * (percent // 5) + "░" * (20 - (percent // 5))
    
    return {
        "name": goal_name, "target": goal_amount, "collected": collected,
        "percent": percent, "bars": bars, "remaining": max(0, goal_amount - collected)
    }


def update_goal_sync(goal_name: str = None, goal_amount: int = None) -> bool:
    """Обновить настройки цели"""
    if goal_amount is not None and (not isinstance(goal_amount, int) or goal_amount < 0):
        raise ValueError("goal_amount должен быть >= 0")
    
    try:
        with get_db_cursor() as cursor:
            updates, params = [], []
            if goal_name is not None: updates.append("goal_name = ?"); params.append(goal_name)
            if goal_amount is not None: updates.append("goal_amount = ?"); params.append(goal_amount)
            
            if not updates: return False
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(1)
            cursor.execute(f"UPDATE settings SET {', '.join(updates)} WHERE id = ?", params)
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"❌ Ошибка обновления цели: {e}")
        return False


# ============ АСИНХРОННЫЕ ОБЁРТКИ ============

async def init_db(): return await asyncio.to_thread(init_database)
async def register_user(user_id, username=None, first_name=None, last_name=None): return await asyncio.to_thread(register_user_sync, user_id, username, first_name, last_name)
async def get_user(user_id): return await asyncio.to_thread(get_user_sync, user_id)
async def get_all_gifts(active_only=True): return await asyncio.to_thread(get_all_gifts_sync, active_only)
async def get_gift_by_id(gift_id): return await asyncio.to_thread(get_gift_by_id_sync, gift_id)
async def add_gift(name, price, description="", icon="🎁", is_active=1): return await asyncio.to_thread(add_gift_sync, name, price, description, icon, is_active)
async def update_gift(gift_id, name=None, price=None, description=None, icon=None, is_active=None): return await asyncio.to_thread(update_gift_sync, gift_id, name, price, description, icon, is_active)
async def create_order(user_id, gift_id, amount, username=None): return await asyncio.to_thread(create_order_sync, user_id, gift_id, amount, username)
async def get_pending_orders(limit=100): return await asyncio.to_thread(get_pending_orders_sync, limit)
async def get_all_orders(limit=100): return await asyncio.to_thread(get_all_orders_sync, limit)
async def get_order_by_id(order_id): return await asyncio.to_thread(get_order_by_id_sync, order_id)
async def get_order(order_id): return await asyncio.to_thread(get_order_by_id_sync, order_id)  # Алиас для admin.py
async def confirm_order(order_id, confirmed_by=None): return await asyncio.to_thread(confirm_order_sync, order_id, confirmed_by)
async def reject_order(order_id, confirmed_by=None): return await asyncio.to_thread(reject_order_sync, order_id, confirmed_by)
async def cancel_order(order_id): return await asyncio.to_thread(cancel_order_sync, order_id)
async def add_transaction(user_id, gift_id, amount, payment_method=None, order_id=None): return await asyncio.to_thread(add_transaction_sync, user_id, gift_id, amount, payment_method, order_id)
async def update_transaction_status(transaction_id, status, confirmed_by=None): return await asyncio.to_thread(update_transaction_status_sync, transaction_id, status, confirmed_by)
async def get_pending_transactions(limit=50): return await asyncio.to_thread(get_pending_transactions_sync, limit)
async def get_all_transactions(limit=100, status=None): return await asyncio.to_thread(get_all_transactions_sync, limit, status)
async def update_top_heroes(user_id, amount, username=None): return await asyncio.to_thread(update_top_heroes_sync, user_id, amount, username)
async def get_top_heroes(limit=10): return await asyncio.to_thread(get_top_heroes_sync, limit)
async def add_gallery_photo(file_id, description="", added_by=None): return await asyncio.to_thread(add_gallery_photo_sync, file_id, description, added_by)
async def get_gallery_photos(limit=50): return await asyncio.to_thread(get_gallery_photos_sync, limit)
async def delete_gallery_photo(photo_id): return await asyncio.to_thread(delete_gallery_photo_sync, photo_id)
async def is_admin(user_id): return await asyncio.to_thread(is_admin_sync, user_id)
async def is_super_admin(user_id): return await asyncio.to_thread(is_super_admin_sync, user_id)
async def add_admin(user_id, added_by=None): return await asyncio.to_thread(add_admin_sync, user_id, added_by)
async def remove_admin(user_id): return await asyncio.to_thread(remove_admin_sync, user_id)
async def log_admin_action(admin_id, action, details=None): return await asyncio.to_thread(log_admin_action_sync, admin_id, action, details)
async def get_statistics(): return await asyncio.to_thread(get_statistics_sync)
async def get_stats(): return await asyncio.to_thread(get_stats_sync)
async def update_stats_cache(): return await asyncio.to_thread(update_stats_cache_sync)
async def get_goal_progress(): return await asyncio.to_thread(get_goal_progress_sync)
async def update_goal(goal_name=None, goal_amount=None): return await asyncio.to_thread(update_goal_sync, goal_name, goal_amount)


# ============ ЭКСПОРТ ============
__all__ = [
    'init_db', 'init_database', 'get_db_connection', 'get_db_cursor',
    'register_user', 'register_user_sync', 'get_user', 'get_user_sync',
    'get_all_gifts', 'get_all_gifts_sync', 'get_gift_by_id', 'get_gift_by_id_sync',
    'add_gift', 'add_gift_sync', 'update_gift', 'update_gift_sync',
    'create_order', 'create_order_sync', 'get_pending_orders', 'get_pending_orders_sync',
    'get_all_orders', 'get_all_orders_sync', 'get_order_by_id', 'get_order_by_id_sync',
    'get_order', 'get_order_sync',  # Добавлено для совместимости
    'confirm_order', 'confirm_order_sync', 'reject_order', 'reject_order_sync',
    'cancel_order', 'cancel_order_sync',
    'add_transaction', 'add_transaction_sync', 'update_transaction_status', 'update_transaction_status_sync',
    'get_pending_transactions', 'get_pending_transactions_sync', 'get_all_transactions', 'get_all_transactions_sync',
    'update_top_heroes', 'update_top_heroes_sync', 'get_top_heroes', 'get_top_heroes_sync',
    'add_gallery_photo', 'add_gallery_photo_sync', 'get_gallery_photos', 'get_gallery_photos_sync',
    'delete_gallery_photo', 'delete_gallery_photo_sync',
    'is_admin', 'is_admin_sync', 'is_super_admin', 'is_super_admin_sync',
    'add_admin', 'add_admin_sync', 'remove_admin', 'remove_admin_sync',
    'log_admin_action', 'log_admin_action_sync',
    'get_statistics', 'get_statistics_sync', 'get_stats', 'get_stats_sync',
    'update_stats_cache', 'update_stats_cache_sync',
    'get_goal_progress', 'get_goal_progress_sync', 'update_goal', 'update_goal_sync'
]

# ============ ИНИЦИАЛИЗАЦИЯ ============
init_database()
