import aiosqlite
import os
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


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
        # Убеждаемся, что папка существует
        await ensure_db_directory()
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Включаем поддержку внешних ключей
            await db.execute("PRAGMA foreign_keys = ON")
            
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
                    photo_id TEXT,
                    category TEXT,
                    sort_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # === ТАБЛИЦА ТРАНЗАКЦИЙ (ЗАКАЗЫ) ===
            # ВНИМАНИЕ: больше нет поля fee! Весь донат распределяется по долям
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    gift_id INTEGER,
                    gift_name TEXT,
                    amount INTEGER NOT NULL,
                    payment_id TEXT,
                    payment_system TEXT DEFAULT 'donatepay',
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                )
            """)
            
            # === ТАБЛИЦА ГАЛЕРЕИ (ФОТО ДЛЯ ПОСТОВ) ===
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
            
            # === ТАБЛИЦА СТАТИСТИКИ (КЭШ) ===
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info(f"✅ База данных инициализирована: {DB_PATH}")
        
        # Заполняем подарки, если таблица пустая
        await init_gifts()
        
        # Обновляем статистику
        await update_cached_stats()
        
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
                    ("По приколу", 222, "Просто так, для настроения", "default"),
                    ("Кофеек", 300, "Чашечка ароматного кофе ☕", "food"),
                    ("На сижку", 500, "Для перекура после катки 🚬", "default"),
                    ("Вкусняшки Марсику", 1111, "Коту на вкусняшки 🐱", "pet"),
                    ("Вклад в биполярку", 1222, "Поддержка ментального здоровья 💊", "default"),
                    ("Новые фотки", 1555, "Эксклюзивные фото в подарок 📸", "content"),
                    ("Пакет киндеров", 2000, "Сюрприз для сладкоежек 🍫", "food"),
                    ("Двойной пакет киндеров", 3333, "Двойная порция сюрприза 🍫🍫", "food"),
                    ("На психушку", 4444, "Запасной план 🏥", "default"),
                    ("На кофточку", 5000, "Обновка в гардероб 👕", "clothes"),
                    ("Продать душу дьяволу", 6666, "Рискованное вложение 😈", "special"),
                    ("На кейсики в КС", 10000, "Кейсы, кейсы, кейсы 🎁", "game"),
                    ("Татушка", 15000, "Новая татуировка 🖤", "special"),
                    ("Косплей на стрим", 20000, "Косплей в следующий стрим 🎭", "content"),
                    ("Нож в КС", 25000, "Красивый нож для красивых фрагов 🔪", "game"),
                    ("НА МЕЧТУ", 150000, "Самый крупный вклад в мечту ✨", "special")
                ]
                
                for idx, (name, price, desc, category) in enumerate(gifts):
                    await db.execute(
                        """INSERT INTO gifts (name, price, description, category, sort_order, is_active) 
                           VALUES (?, ?, ?, ?, ?, 1)""",
                        (name, price, desc, category, idx)
                    )
                await db.commit()
                logger.info(f"✅ Добавлено {len(gifts)} подарков в базу")
                
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации подарков: {e}")


async def update_cached_stats():
    """Обновляет кэшированную статистику"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Общее количество заказов
            cursor = await db.execute("SELECT COUNT(*) FROM transactions WHERE status = 'completed'")
            total_orders = (await cursor.fetchone())[0]
            
            # Общая сумма (весь оборот)
            cursor = await db.execute("SELECT SUM(amount) FROM transactions WHERE status = 'completed'")
            total_amount = (await cursor.fetchone())[0] or 0
            
            # Сохраняем в таблицу stats
            await db.execute(
                "INSERT OR REPLACE INTO stats (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                ("total_orders", str(total_orders))
            )
            await db.execute(
                "INSERT OR REPLACE INTO stats (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                ("total_amount", str(total_amount))
            )
            await db.commit()
            
    except Exception as e:
        logger.error(f"Ошибка обновления статистики: {e}")


async def get_user(user_id: int):
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
    """Добавить пользователя"""
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


async def get_all_gifts():
    """Получить все активные подарки"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id, name, price, description, category FROM gifts WHERE is_active = 1 ORDER BY sort_order, price"
            )
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2], "description": r[3], "category": r[4]} for r in rows]
    except Exception as e:
        logger.error(f"Ошибка get_all_gifts: {e}")
        return []


async def get_gift_by_id(gift_id: int):
    """Получить подарок по ID"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id, name, price, description, category, photo_id FROM gifts WHERE id = ? AND is_active = 1",
                (gift_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "name": row[1],
                    "price": row[2],
                    "description": row[3],
                    "category": row[4],
                    "photo_id": row[5]
                }
            return None
    except Exception as e:
        logger.error(f"Ошибка get_gift_by_id: {e}")
        return None


async def add_transaction(user_id: int, username: str, gift_id: int, gift_name: str, amount: int, payment_id: str = None):
    """Добавить транзакцию (без комиссии, весь донат распределяется по долям)"""
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
            
            # Обновляем кэш статистики
            await update_cached_stats()
            
            return transaction_id
    except Exception as e:
        logger.error(f"Ошибка add_transaction: {e}")
        return None


async def get_all_transactions(limit: int = 50):
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


async def get_stats():
    """Получить статистику (общий оборот без вычета комиссии)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Количество заказов
            cursor = await db.execute("SELECT COUNT(*) FROM transactions WHERE status = 'completed'")
            total_orders = (await cursor.fetchone())[0]
            
            # Общая сумма (весь оборот)
            cursor = await db.execute("SELECT SUM(amount) FROM transactions WHERE status = 'completed'")
            total_amount = (await cursor.fetchone())[0] or 0
            
            # Количество пользователей
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            return {
                "total_orders": total_orders,
                "total_amount": total_amount,
                "total_users": total_users
            }
    except Exception as e:
        logger.error(f"Ошибка get_stats: {e}")
        return {
            "total_orders": 0,
            "total_amount": 0,
            "total_users": 0
        }


async def add_gallery_photo(photo_id: str, caption: str, created_by: int):
    """Добавить фото в галерею"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO gallery (photo_id, caption, created_by, is_active) VALUES (?, ?, ?, 1)",
                (photo_id, caption, created_by)
            )
            await db.commit()
            logger.info(f"✅ Фото добавлено в галерею: {photo_id}")
    except Exception as e:
        logger.error(f"Ошибка add_gallery_photo: {e}")


async def get_gallery_photos(limit: int = 20):
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


async def clear_transactions():
    """Очистить все транзакции (только для супер-админа)"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM transactions")
            await db.commit()
            logger.warning("⚠️ Все транзакции удалены")
            await update_cached_stats()
    except Exception as e:
        logger.error(f"Ошибка clear_transactions: {e}")
