import os
import aiosqlite
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import DB_PATH, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)

# ============ ПОДКЛЮЧЕНИЕ К БД ============

async def get_db():
    """Получение соединения с БД"""
    return aiosqlite.connect(DB_PATH)

async def init_db():
    """Инициализация базы данных: создание всех таблиц"""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"✅ Создана папка для БД: {db_dir}")
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        
        await db.execute("""
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
        
        await db.execute("""
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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gift_id INTEGER NOT NULL,
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
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS top_heroes (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                total_amount INTEGER DEFAULT 0,
                last_donate TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gallery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT NOT NULL,
                description TEXT,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                added_by INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_transactions_status ON transactions(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_top_heroes_amount ON top_heroes(total_amount DESC)")
        
        await db.commit()
        await init_default_gifts()
        logger.info("✅ База данных инициализирована")

async def init_default_gifts():
    """Добавление стандартных подарков, если таблица пуста"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM gifts")
        count = await cursor.fetchone()
        
        if count[0] == 0:
            default_gifts = [
                ("Чиби-арт", "Милая аватарка с Ланой в чиби-стиле", 500, "🎨"),
                ("Скринсейвер", "Эксклюзивный скринсейвер для телефона", 1000, "📱"),
                ("Видеопривет", "Лана запишет личное видео-приветствие", 3000, "🎥"),
                ("Татушка", "Настоящая татуировка от Ланы", 15000, "💉"),
                ("Косплей на стрим", "Лана сделает косплей по твоему заказу", 20000, "🎭"),
                ("Нож в КС", "Скин для Counter-Strike", 25000, "🔪"),
                ("Именной стрим", "Стрим с твоим ником в названии", 50000, "🎮"),
                ("НА МЕЧТУ", "Поддержка новой мечты Ланы", 150000, "💫"),
            ]
            
            for name, desc, price, icon in default_gifts:
                await db.execute("""
                    INSERT INTO gifts (name, description, price, icon)
                    VALUES (?, ?, ?, ?)
                """, (name, desc, price, icon))
            
            await db.commit()
            logger.info(f"✅ Добавлено {len(default_gifts)} подарков в базу")

# ============ ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ============

async def register_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Регистрация или обновление пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_active)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, first_name, last_name, datetime.now()))
        await db.commit()

async def update_user_activity(user_id: int):
    """Обновление времени последней активности"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET last_active = ? WHERE user_id = ?
        """, (datetime.now(), user_id))
        await db.commit()

# ============ ФУНКЦИИ ДЛЯ ПОДАРКОВ ============

async def get_all_gifts(active_only: bool = True) -> List[Dict[str, Any]]:
    """Получить все подарки"""
    async with aiosqlite.connect(DB_PATH) as db:
        if active_only:
            cursor = await db.execute("SELECT * FROM gifts WHERE is_active = 1 ORDER BY price")
        else:
            cursor = await db.execute("SELECT * FROM gifts ORDER BY price")
        
        rows = await cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": row[3],
                "icon": row[4],
                "is_active": row[5],
                "created_at": row[6]
            }
            for row in rows
        ]

async def get_gift_by_id(gift_id: int) -> Optional[Dict[str, Any]]:
    """Получить подарок по ID"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM gifts WHERE id = ?", (gift_id,))
        row = await cursor.fetchone()
        
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "price": row[3],
                "icon": row[4],
                "is_active": row[5],
                "created_at": row[6]
            }
        return None

async def add_gift(name: str, price: int, description: str = "", icon: str = "🎁") -> int:
    """Добавить новый подарок"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO gifts (name, description, price, icon)
            VALUES (?, ?, ?, ?)
        """, (name, description, price, icon))
        await db.commit()
        return cursor.lastrowid

async def update_gift(gift_id: int, **kwargs):
    """Обновить информацию о подарке"""
    async with aiosqlite.connect(DB_PATH) as db:
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        if fields:
            query = f"UPDATE gifts SET {', '.join(fields)} WHERE id = ?"
            values.append(gift_id)
            await db.execute(query, values)
            await db.commit()

# ============ ФУНКЦИИ ДЛЯ ТРАНЗАКЦИЙ ============

async def add_transaction(user_id: int, gift_id: int, amount: int, payment_method: str = None) -> int:
    """Добавить новую транзакцию (заказ)"""
    async with aiosqlite.connect(DB_PATH) as db:
        gift = await get_gift_by_id(gift_id)
        gift_name = gift['name'] if gift else f"Подарок #{gift_id}"
        
        cursor = await db.execute("""
            INSERT INTO transactions (user_id, gift_id, gift_name, amount, status, payment_method)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (user_id, gift_id, gift_name, amount, payment_method))
        await db.commit()
        return cursor.lastrowid

async def create_transaction(user_id: int, gift_id: int, amount: int, gift_name: str) -> int:
    """Создать новую транзакцию (альтернативная функция)"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO transactions (user_id, gift_id, gift_name, amount, status)
            VALUES (?, ?, ?, ?, 'pending')
        """, (user_id, gift_id, gift_name, amount))
        await db.commit()
        return cursor.lastrowid

async def update_transaction_status(transaction_id: int, status: str, confirmed_by: int = None):
    """Обновить статус транзакции"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE transactions 
            SET status = ?, confirmed_at = ?, confirmed_by = ?
            WHERE id = ?
        """, (status, datetime.now() if status == 'paid' else None, confirmed_by, transaction_id))
        await db.commit()

async def get_pending_transactions(limit: int = 50) -> List[Dict[str, Any]]:
    """Получить ожидающие подтверждения транзакции"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT t.*, u.username, u.first_name
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.user_id
            WHERE t.status = 'pending'
            ORDER BY t.created_at DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        
        transactions = []
        for row in rows:
            transactions.append({
                "id": row[0],
                "user_id": row[1],
                "gift_id": row[2],
                "gift_name": row[3],
                "amount": row[4],
                "status": row[5],
                "payment_method": row[6],
                "payment_details": row[7],
                "created_at": row[8],
                "confirmed_at": row[9],
                "confirmed_by": row[10],
                "username": row[11] if len(row) > 11 else None,
                "first_name": row[12] if len(row) > 12 else None,
            })
        return transactions

async def get_all_transactions(limit: int = 100) -> List[Dict[str, Any]]:
    """Получить все транзакции"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT t.*, u.username
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.user_id
            ORDER BY t.created_at DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "user_id": row[1],
                "gift_id": row[2],
                "gift_name": row[3],
                "amount": row[4],
                "status": row[5],
                "created_at": row[8],
                "username": row[11] if len(row) > 11 else None,
            }
            for row in rows
        ]

# ============ ФУНКЦИИ ДЛЯ ТОПА ГЕРОЕВ ============

async def update_top_heroes(user_id: int, amount: int, username: str = None):
    """Обновить топ героев после доната"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT total_amount FROM top_heroes WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        
        if row:
            new_total = row[0] + amount
            await db.execute("""
                UPDATE top_heroes 
                SET total_amount = ?, last_donate = ?, updated_at = ?, username = COALESCE(?, username)
                WHERE user_id = ?
            """, (new_total, datetime.now(), datetime.now(), username, user_id))
        else:
            await db.execute("""
                INSERT INTO top_heroes (user_id, username, total_amount, last_donate)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, amount, datetime.now()))
        
        await db.commit()
        
        cursor = await db.execute("""
            SELECT user_id, total_amount FROM top_heroes 
            ORDER BY total_amount DESC 
            LIMIT 3
        """)
        top3 = await cursor.fetchall()
        
        for i, (uid, _) in enumerate(top3):
            if uid == user_id:
                return i + 1
        return None

async def update_top_hero(user_id: int, amount: int, username: str = None):
    """Обновить топ героев (алиас для update_top_heroes)"""
    return await update_top_heroes(user_id, amount, username)

async def get_top_heroes(limit: int = 10) -> List[Dict[str, Any]]:
    """Получить топ героев"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, username, total_amount, last_donate
            FROM top_heroes 
            ORDER BY total_amount DESC 
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        
        return [
            {
                "user_id": row[0],
                "username": row[1],
                "total_amount": row[2],
                "last_donate": row[3]
            }
            for row in rows
        ]

async def get_user_rank(user_id: int) -> Optional[int]:
    """Получить место пользователя в топе"""
    heroes = await get_top_heroes(limit=100)
    for i, hero in enumerate(heroes):
        if hero["user_id"] == user_id:
            return i + 1
    return None

# ============ ФУНКЦИИ ДЛЯ ГАЛЕРЕИ ============

async def add_gallery_photo(file_id: str, description: str = "", added_by: int = None) -> int:
    """Добавить фото в галерею"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO gallery (file_id, description, added_by)
            VALUES (?, ?, ?)
        """, (file_id, description, added_by))
        await db.commit()
        return cursor.lastrowid

async def get_gallery_photos(limit: int = 50) -> List[Dict[str, Any]]:
    """Получить фото из галереи"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT id, file_id, description, added_by, added_at
            FROM gallery
            ORDER BY added_at DESC
            LIMIT ?
        """, (limit,))
        rows = await cursor.fetchall()
        
        return [
            {
                "id": row[0],
                "file_id": row[1],
                "description": row[2],
                "added_by": row[3],
                "added_at": row[4]
            }
            for row in rows
        ]

async def delete_gallery_photo(photo_id: int) -> bool:
    """Удалить фото из галереи"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM gallery WHERE id = ?", (photo_id,))
        await db.commit()
        return cursor.rowcount > 0

# ============ АДМИН ФУНКЦИИ ============

async def is_super_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь супер-админом"""
    return user_id == SUPER_ADMIN_ID

async def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом или менеджером"""
    if user_id == SUPER_ADMIN_ID:
        return True
    if user_id == SUPPORT_ADMIN_ID:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row is not None

async def add_admin(user_id: int, username: str = None) -> bool:
    """Добавить администратора (только для супер-админа)"""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT OR REPLACE INTO admins (user_id, username, added_by)
                VALUES (?, ?, ?)
            """, (user_id, username, SUPER_ADMIN_ID))
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления админа: {e}")
            return False

async def remove_admin(user_id: int) -> bool:
    """Удалить администратора"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0

async def get_all_admins() -> List[Dict[str, Any]]:
    """Получить список всех администраторов"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, username, added_by, added_at 
            FROM admins 
            ORDER BY added_at DESC
        """)
        rows = await cursor.fetchall()
        return [
            {
                "user_id": row[0],
                "username": row[1],
                "added_by": row[2],
                "added_at": row[3]
            }
            for row in rows
        ]

# ============ ФУНКЦИИ ДЛЯ СТАТИСТИКИ ============

_cache_stats = {}

async def update_stats_cache():
    """Обновить кэш статистики"""
    global _cache_stats
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM transactions WHERE status = 'paid'")
        total_donations = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT SUM(amount) FROM transactions WHERE status = 'paid'")
        total_amount = (await cursor.fetchone())[0] or 0
        
        first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cursor = await db.execute("""
            SELECT SUM(amount) FROM transactions 
            WHERE status = 'paid' AND created_at >= ?
        """, (first_day,))
        month_amount = (await cursor.fetchone())[0] or 0
        
        _cache_stats = {
            "total_users": total_users,
            "total_donations": total_donations,
            "total_amount": total_amount,
            "month_amount": month_amount,
            "updated_at": datetime.now()
        }
        
        logger.info("✅ Кэш статистики обновлён")
        return _cache_stats

async def get_stats() -> Dict[str, Any]:
    """Получить статистику (из кэша)"""
    global _cache_stats
    if not _cache_stats:
        await update_stats_cache()
    return _cache_stats

# ============ ФУНКЦИИ ДЛЯ ЛОГОВ ============

async def log_admin_action(admin_id: int, action: str, details: str = None):
    """Записать действие админа в лог"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO admin_logs (admin_id, action, details)
            VALUES (?, ?, ?)
        """, (admin_id, action, details))
        await db.commit()
