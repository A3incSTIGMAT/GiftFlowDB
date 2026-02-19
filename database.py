import asyncpg
import os

DATABASE_URL = os.getenv('DATABASE_URL')
pool = None

async def init_db():
    global pool
    try:
        pool = await asyncpg.create_pool(DATABASE_URL)
        async with pool.acquire() as conn:
            # Таблица пользователей
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance REAL DEFAULT 0,
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица транзакций
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    gift_name TEXT,
                    amount REAL,
                    fee REAL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица подарков
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS gifts (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    price REAL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Проверка наличия подарков
            res = await conn.fetchval("SELECT count(*) FROM gifts")
            if res == 0:
                gifts_data = [
                    ("По приколу", 222, "Просто чтобы поднять настроение 😄"),
                    ("Кофеек", 300, "На чашечку вкусного кофе ☕"),
                    ("На сижку", 500, "На уютный вечер дома 🛋️"),
                    ("Вкусняшки Марсику", 1111, "Котик скажет спасибо и помурчит 🐱"),
                    ("Вклад в биполярку", 1222, "На мои эмоциональные горки 🎢 (шутка)"),
                    ("Новые фотки", 1555, "На контент для канала 📸"),
                    ("Пакет киндеров", 2000, "Соберу коллекцию и похрущу 🍫"),
                    ("Двойной пакет киндеров", 3333, "Хруст на весь канал 🍫🍫"),
                    ("На психушку", 4444, "На ментальное здоровье и терапию 🧠"),
                    ("На кофточку", 5000, "На обновку гардероба 👚"),
                    ("Продать душу дьяволу", 6666, "На маленькие тёмные желания 😈"),
                    ("На кейсики в КС", 10000, "На игровой контент / скин 🎮"),
                    ("Татушка", 15000, "Выберешь эскиз вместе со мной 🎨"),
                    ("Косплей на стрим", 20000, "Голосование за образ в эфире 🎭"),
                    ("Нож в КС", 25000, "Мечта геймера (скин) 🗡️"),
                    ("НА МЕЧТУ", 150000, "Большая цель, спасибо за веру ✨")
                ]
                for g in gifts_data:
                    await conn.execute(
                        "INSERT INTO gifts (name, price, description) VALUES ($1, $2, $3)",
                        g[0], g[1], g[2]
                    )
                print("✅ База подарков успешно заполнена!")
        
        print("✅ База данных подключена!")
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        raise

async def add_user(user_id, username):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id, username) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING",
            user_id, username
        )

async def get_user(user_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def add_transaction(user_id, gift_name, amount, fee):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO transactions (user_id, gift_name, amount, fee) VALUES ($1, $2, $3, $4)",
            user_id, gift_name, amount, fee
        )

async def get_all_gifts():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM gifts WHERE is_active = TRUE ORDER BY price ASC")

async def get_all_transactions():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM transactions ORDER BY created_at DESC")

async def get_user_transactions(user_id):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM transactions WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )


