import aiosqlite
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from config import DB_PATH

logger = logging.getLogger(__name__)

# Кэш для статистики
_stats_cache: Dict[str, Any] = {"data": None, "timestamp": 0}


async def ensure_db_directory():
    """Создаёт папку для базы данных, если её нет"""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"✅ Создана папка для БД: {db_dir}")
        except Exception as e:
            logger.error(f"❌ Не удалось создать папку {db_dir}: {e}")
            raise


async def init_db():
    """Инициализация базы данных со всеми таблицами"""
    try:
        await ensure_db_directory()
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("PRAGMA journal_mode = WAL")
            
            # === ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # === ТАБЛИЦА ПОДАРКОВ ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS gifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT,
                    icon TEXT DEFAULT '🎁',
                    category TEXT,
                    sort_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # === ТАБЛИЦА ТРАНЗАКЦИЙ ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    gift_id INTEGER,
                    gift_name TEXT,
                    amount INTEGER NOT NULL,
                    payment_id TEXT,
                    payment_system TEXT DEFAULT 'ozon',
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            
            # === ТАБЛИЦА ГАЛЕРЕИ ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS gallery (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo_id TEXT NOT NULL,
                    caption TEXT,
                    created_by INTEGER,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            
            # === ТАБЛИЦА СТАТИСТИКИ ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # === ТАБЛИЦА ЛОГОВ АДМИНОВ ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info(f"✅ База данных инициализирована: {DB_PATH}")
        
        await init_gifts()
        await update_stats_cache()
        
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации БД: {e}")
        raise


async def init_gifts():
    """Заполнение подарков при пустой таблице"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM gifts WHERE is_active = 1")
            count = (await cursor.fetchone())[0]
            
            if count == 0:
                gifts = [
                    # МИКРО-ДОНАТЫ (10-100₽)
                    ("🍬 Конфетка", 10, "Маленькая сладость для настроения 🍬", "🍬", "micro"),
                    ("❤️ Лайк в чат", 20, "Лайк в прямом эфире! ❤️", "❤️", "micro"),
                    ("🍪 Печенька", 30, "К чайку в перерыве 🍪", "🍪", "micro"),
                    ("🧸 Обнимашка", 50, "Тёплый виртуальный хаг 🧸", "🧸", "micro"),
                    ("☕ Мини-кофе", 50, "Маленькая порция бодрости ☕", "☕", "micro"),
                    ("🎵 Заказ трека", 75, "Любую песню на стрим 🎵", "🎵", "micro"),
                    ("😺 Корм Марсику", 100, "Котику на вкусняшки 🐱", "😺", "pet"),
                    ("📢 Упоминание", 100, "Твой ник в прямом эфире! 📢", "📢", "micro"),
                    
                    # СРЕДНИЕ ДОНАТЫ (150-500₽)
                    ("☕ Кофеек", 150, "Чашечка ароматного кофе ☕", "☕", "food"),
                    ("🎮 Выбор карты", 150, "Ты выбираешь следующую карту в CS 🎮", "🎮", "game"),
                    ("📷 Фото в сторис", 200, "Твоё имя в Instagram Stories 📷", "📷", "content"),
                    ("🎲 Кинуть кубик", 200, "Стримерша выполняет случайное действие 🎲", "🎲", "game"),
                    ("🎁 Кейс в КС", 300, "Открываем кейс вместе! 🎁", "🎁", "game"),
                    ("🔥 Панчлайн", 350, "Смешная фраза в твою честь 🔥", "🔥", "default"),
                    ("🐱 Игрушка Марсику", 400, "Новая игрушка для котика 🐱", "🐱", "pet"),
                    ("🎬 Реакция на мем", 500, "Стримерша реагирует на твой мем 🎬", "🎬", "content"),
                    
                    # ОСТАЛЬНЫЕ ПОДАРКИ
                    ("По приколу", 222, "Просто так, для настроения", "🎲", "default"),
                    ("Вкусняшки Марсику", 1111, "Коту на вкусняшки 🐱", "🍖", "pet"),
                    ("Вклад в биполярку", 1222, "Поддержка ментального здоровья 💊", "💊", "default"),
                    ("Новые фотки", 1555, "Эксклюзивные фото в подарок 📸", "📸", "content"),
                    ("Пакет киндеров", 2000, "Сюрприз для сладкоежек 🍫", "🍫", "food"),
                    ("Двойной пакет киндеров", 3333, "Двойная порция сюрприза 🍫🍫", "🍫", "food"),
                    ("На психушку", 4444, "Запасной план 🏥", "🏥", "default"),
                    ("На кофточку", 5000, "Обновка в гардероб 👕", "👕", "clothes"),
                    ("Продать душу дьяволу", 6666, "Рискованное вложение 😈", "😈", "special"),
                    ("На кейсики в КС", 10000, "Кейсы, кейсы, кейсы 🎁", "🎁", "game"),
                    ("Татушка", 15000, "Новая татуировка 🖤", "🖤", "special"),
                    ("Косплей на стрим", 20000, "Косплей в следующий стрим 🎭", "🎭", "content"),
                    ("Нож в КС", 25000, "Красивый нож для красивых фрагов 🔪", "🔪", "game"),
                    ("НА МЕЧТУ", 150000, "Самый крупный вклад в мечту ✨", "✨", "special")
                ]
                
                for idx, (name, price, desc, icon, category) in enumerate(gifts):
                    await db.execute(
                        """INSERT INTO gifts (name, price, description, icon, category, sort_order, is_active) 
                           VALUES (?, ?, ?, ?, ?, ?, 1)""",
                        (name, price, desc, icon, category, idx)
                    )
                await db.commit()
                logger.info(f"✅ Добавлено {len(gifts)} подарков в базу")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации подарков: {e}")


# ========== ПОЛЬЗОВАТЕЛИ ==========
async def get_user(user_id: int) -> Optional[Dict]:
    """Получить пользователя по ID"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id, username, first_name, last_name, is_admin, created_at FROM users WHERE id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "username": row[1],
                    "first_name": row[2],
                    "last_name": row[3],
                    "is_admin": row[4],
                    "created_at": row[5]
                }
            return None
    except Exception as e:
        logger.error(f"Ошибка get_user: {e}")
        return None


async def add_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Добавить или обновить пользователя"""
    try:
        from config import ADMIN_IDS
        
        is_admin = 1 if user_id in ADMIN_IDS else 0
        
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT OR REPLACE INTO users (id, username, first_name, last_name, is_admin, updated_at) 
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (user_id, username, first_name, last_name, is_admin)
            )
            await db.commit()
            logger.info(f"✅ Пользователь {user_id} добавлен/обновлён")
    except Exception as e:
        logger.error(f"Ошибка add_user: {e}")


# ========== ПОДАРКИ ==========
async def get_all_gifts() -> List[Dict]:
    """Получить все активные подарки"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id, name, price, description, icon FROM gifts WHERE is_active = 1 ORDER BY sort_order, price"
            )
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2], "description": r[3], "icon": r[4]} for r in rows]
    except Exception as e:
        logger.error(f"Ошибка get_all_gifts: {e}")
        return []


async def get_gift_by_id(gift_id: int) -> Optional[Dict]:
    """Получить подарок по ID"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id, name, price, description, icon FROM gifts WHERE id = ? AND is_active = 1",
                (gift_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "price": row[2],
                    "description": row[3],
                    "icon": row[4]
                }
            return None
    except Exception as e:
        logger.error(f"Ошибка get_gift_by_id: {e}")
        return None


async def add_gift(name: str, price: int, description: str, icon: str = "🎁", category: str = "default") -> bool:
    """Добавить новый подарок"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT MAX(sort_order) FROM gifts")
            max_order = (await cursor.fetchone())[0] or 0
            new_order = max_order + 1
            
            await db.execute(
                """INSERT INTO gifts (name, price, description, icon, category, sort_order, is_active) 
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (name, price, description, icon, category, new_order)
            )
            await db.commit()
            logger.info(f"✅ Добавлен новый подарок: {name} ({price}₽)")
            return True
    except Exception as e:
        logger.error(f"Ошибка add_gift: {e}")
        return False


# ========== ТРАНЗАКЦИИ ==========
async def add_transaction(user_id: int, username: str, gift_id: int, gift_name: str, amount: int, payment_id: str = None) -> Optional[int]:
    """Добавить транзакцию"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO transactions (user_id, username, gift_id, gift_name, amount, payment_id, status, completed_at) 
                   VALUES (?, ?, ?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)""",
                (user_id, username, gift_id, gift_name, amount, payment_id)
            )
            await db.commit()
            transaction_id = cursor.lastrowid
            logger.info(f"✅ Транзакция {transaction_id} добавлена: {amount}₽ от {username}")
            await update_stats_cache()
            return transaction_id
    except Exception as e:
        logger.error(f"Ошибка add_transaction: {e}")
        return None


async def get_all_transactions(limit: int = 50) -> List[Dict]:
    """Получить последние транзакции"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT user_id, username, gift_name, amount, status, created_at, completed_at 
                   FROM transactions ORDER BY created_at DESC LIMIT ?""",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [{
                "user_id": r[0],
                "username": r[1],
                "gift_name": r[2],
                "amount": r[3],
                "status": r[4],
                "created_at": r[5],
                "completed_at": r[6]
            } for r in rows]
    except Exception as e:
        logger.error(f"Ошибка get_all_transactions: {e}")
        return []


# ========== СТАТИСТИКА ==========
async def get_stats() -> Dict[str, Any]:
    """Получить статистику"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM transactions WHERE status = 'completed'")
            total_orders = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT SUM(amount) FROM transactions WHERE status = 'completed'")
            total_amount = (await cursor.fetchone())[0] or 0
            
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            return {
                "total_orders": total_orders,
                "total_amount": total_amount,
                "total_users": total_users
            }
    except Exception as e:
        logger.error(f"Ошибка get_stats: {e}")
        return {"total_orders": 0, "total_amount": 0, "total_users": 0}


async def update_stats_cache() -> Optional[Dict]:
    """Обновление кэша статистики"""
    global _stats_cache
    try:
        stats = await get_stats()
        _stats_cache["data"] = stats
        _stats_cache["timestamp"] = asyncio.get_event_loop().time()
        logger.info("✅ Кэш статистики обновлён")
        return stats
    except Exception as e:
        logger.error(f"Ошибка обновления кэша статистики: {e}")
        return None


def get_stats_cached() -> Optional[Dict]:
    """Получение статистики из кэша"""
    if _stats_cache["data"] and (asyncio.get_event_loop().time() - _stats_cache["timestamp"]) < 300:
        return _stats_cache["data"]
    return None


async def clear_transactions() -> bool:
    """Очистить все транзакции (только для супер-админа)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM transactions")
            await db.commit()
            logger.warning("⚠️ Все транзакции удалены")
            await update_stats_cache()
            return True
    except Exception as e:
        logger.error(f"Ошибка clear_transactions: {e}")
        return False


# ========== ГАЛЕРЕЯ ==========
async def add_gallery_photo(photo_id: str, caption: str, created_by: int) -> bool:
    """Добавить фото в галерею"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO gallery (photo_id, caption, created_by, is_active) VALUES (?, ?, ?, 1)",
                (photo_id, caption, created_by)
            )
            await db.commit()
            logger.info(f"✅ Фото добавлено в галерею: {photo_id}")
            return True
    except Exception as e:
        logger.error(f"Ошибка add_gallery_photo: {e}")
        return False


async def get_gallery_photos(limit: int = 20) -> List[Tuple[str, str, str]]:
    """Получить фото из галереи"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT photo_id, caption, created_at FROM gallery WHERE is_active = 1 ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return await cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка get_gallery_photos: {e}")
        return []


async def delete_gallery_photo(photo_id: str) -> bool:
    """Удалить фото из галереи (мягкое удаление)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE gallery SET is_active = 0 WHERE photo_id = ?",
                (photo_id,)
            )
            await db.commit()
            logger.info(f"✅ Фото удалено из галереи: {photo_id}")
            return True
    except Exception as e:
        logger.error(f"Ошибка delete_gallery_photo: {e}")
        return False


# ========== ЛОГИ АДМИНОВ ==========
async def log_admin_action(user_id: int, action: str, details: str = "") -> bool:
    """
    Логирование действий администраторов
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO admin_logs (user_id, action, details) VALUES (?, ?, ?)",
                (user_id, action, details[:500])
            )
            await db.commit()
            
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"[ADMIN ACTION] {timestamp} | {user_id} | {action} | {details[:100]}")
        return True
    except Exception as e:
        logger.error(f"Ошибка log_admin_action: {e}")
        return False


async def get_admin_logs(limit: int = 50) -> List[Dict]:
    """Получить последние логи админов"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, action, details, created_at FROM admin_logs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            return [{
                "user_id": r[0],
                "action": r[1],
                "details": r[2],
                "created_at": r[3]
            } for r in rows]
    except Exception as e:
        logger.error(f"Ошибка get_admin_logs: {e}")
        return []


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def get_db_size() -> int:
    """Получить размер базы данных в байтах"""
    try:
        return os.path.getsize(DB_PATH)
    except Exception:
        return 0


async def vacuum_db() -> bool:
    """Оптимизация базы данных"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("VACUUM")
            logger.info("✅ База данных оптимизирована")
            return True
    except Exception as e:
        logger.error(f"Ошибка vacuum_db: {e}")
        return False
