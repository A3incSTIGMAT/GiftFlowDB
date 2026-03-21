import aiosqlite
import os
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

async def init_db():
    """Инициализация базы данных"""
    try:
        # Создаём папку для базы данных, если её нет
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Создана папка: {db_dir}")
        
        async with aiosqlite.connect(DB_PATH) as db:
            # Пользователи
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Подарки
            await db.execute("""
                CREATE TABLE IF NOT EXISTS gifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    price INTEGER NOT NULL,
                    description TEXT,
                    photo_id TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            # Транзакции
            await db.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    gift_name TEXT,
                    amount INTEGER,
                    fee INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Галерея (фото для постов)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS gallery (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo_id TEXT NOT NULL,
                    caption TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info(f"База данных инициализирована: {DB_PATH}")
        
        # Заполняем подарки, если таблица пустая
        await init_gifts()
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации БД: {e}")
        raise


async def init_gifts():
    """Заполнение подарков при пустой таблице"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM gifts")
            count = (await cursor.fetchone())[0]
            
            if count == 0:
                gifts = [
                    ("По приколу", 222, "Просто так, для настроения"),
                    ("Кофеек", 300, "Чашечка ароматного кофе"),
                    ("На сижку", 500, "Для перекура после катки"),
                    ("Вкусняшки Марсику", 1111, "Коту на вкусняшки 🐱"),
                    ("Вклад в биполярку", 1222, "Поддержка ментального здоровья"),
                    ("Новые фотки", 1555, "Эксклюзивные фото в подарок"),
                    ("Пакет киндеров", 2000, "Сюрприз для сладкоежек"),
                    ("Двойной пакет киндеров", 3333, "Двойная порция сюрприза"),
                    ("На психушку", 4444, "Запасной план"),
                    ("На кофточку", 5000, "Обновка в гардероб"),
                    ("Продать душу дьяволу", 6666, "Рискованное вложение"),
                    ("На кейсики в КС", 10000, "Кейсы, кейсы, кейсы"),
                    ("Татушка", 15000, "Новая татуировка"),
                    ("Косплей на стрим", 20000, "Косплей в следующий стрим"),
                    ("Нож в КС", 25000, "Красивый нож для красивых фрагов"),
                    ("НА МЕЧТУ", 150000, "Самый крупный вклад в мечту")
                ]
                
                for name, price, desc in gifts:
                    await db.execute(
                        "INSERT INTO gifts (name, price, description) VALUES (?, ?, ?)",
                        (name, price, desc)
                    )
                await db.commit()
                logger.info(f"Добавлено {len(gifts)} подарков в базу")
                
    except Exception as e:
        logger.error(f"Ошибка при инициализации подарков: {e}")


async def get_user(user_id: int):
    """Получить пользователя по ID"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка get_user: {e}")
        return None


async def add_user(user_id: int, username: str = None):
    """Добавить пользователя"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка add_user: {e}")


async def get_all_gifts():
    """Получить все активные подарки"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id, name, price, description FROM gifts WHERE is_active = 1"
            )
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "price": r[2], "description": r[3]} for r in rows]
    except Exception as e:
        logger.error(f"Ошибка get_all_gifts: {e}")
        return []


async def get_gift_by_id(gift_id: int):
    """Получить подарок по ID"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT id, name, price, description FROM gifts WHERE id = ? AND is_active = 1",
                (gift_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "name": row[1], "price": row[2], "description": row[3]}
            return None
    except Exception as e:
        logger.error(f"Ошибка get_gift_by_id: {e}")
        return None


async def add_transaction(user_id: int, username: str, gift_name: str, amount: int, fee: int):
    """Добавить транзакцию"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO transactions (user_id, username, gift_name, amount, fee, status) VALUES (?, ?, ?, ?, ?, 'completed')",
                (user_id, username, gift_name, amount, fee)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка add_transaction: {e}")


async def get_all_transactions():
    """Получить все транзакции"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, username, gift_name, amount, fee, created_at FROM transactions ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
            return [{"user_id": r[0], "username": r[1], "gift_name": r[2], "amount": r[3], "fee": r[4], "created_at": r[5]} for r in rows]
    except Exception as e:
        logger.error(f"Ошибка get_all_transactions: {e}")
        return []


async def add_gallery_photo(photo_id: str, caption: str, created_by: int):
    """Добавить фото в галерею"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO gallery (photo_id, caption, created_by) VALUES (?, ?, ?)",
                (photo_id, caption, created_by)
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Ошибка add_gallery_photo: {e}")


async def get_gallery_photos():
    """Получить фото из галереи"""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT photo_id, caption FROM gallery ORDER BY created_at DESC")
            return await cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка get_gallery_photos: {e}")
        return []
