import os
import asyncpg

DATABASE_URL = os.getenv('DATABASE_URL')

async def init_db():
    """Создаёт таблицы в базе данных"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Таблица пользователей
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица подарков
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS gifts (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            price DECIMAL NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица транзакций
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            gift_name TEXT NOT NULL,
            amount DECIMAL NOT NULL,
            fee DECIMAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    await conn.close()
    print("✅ База данных инициализирована")

async def get_user(user_id):
    """Получает пользователя из БД"""
    conn = await asyncpg.connect(DATABASE_URL)
    user = await conn.fetchrow('SELECT * FROM users WHERE user_id = $1', user_id)
    await conn.close()
    return user

async def add_user(user_id, username):
    """Добавляет пользователя в БД"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('INSERT INTO users (user_id, username) VALUES ($1, $2)', user_id, username)
    await conn.close()

async def get_all_gifts():
    """Получает все подарки из БД"""
    conn = await asyncpg.connect(DATABASE_URL)
    gifts = await conn.fetch('SELECT * FROM gifts')
    await conn.close()
    return gifts

async def add_transaction(user_id, gift_name, amount, fee):
    """Добавляет транзакцию в БД"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        'INSERT INTO transactions (user_id, gift_name, amount, fee) VALUES ($1, $2, $3, $4)',
        user_id, gift_name, amount, fee
    )
    await conn.close()

async def get_all_transactions():
    """Получает все транзакции из БД"""
    conn = await asyncpg.connect(DATABASE_URL)
    transactions = await conn.fetch('SELECT * FROM transactions')
    await conn.close()
    return transactions

async def clear_transactions():
    """Очищает таблицу транзакций (сброс статистики)"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("DELETE FROM transactions")
        print("✅ Все транзакции удалены")
    finally:
        await conn.close()

async def get_user_transactions(user_id):
    """Получает транзакции конкретного пользователя"""
    conn = await asyncpg.connect(DATABASE_URL)
    transactions = await conn.fetch('SELECT * FROM transactions WHERE user_id = $1', user_id)
    await conn.close()
    return transactions

async def add_gift(name, price, description):
    """Добавляет подарок в БД"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        'INSERT INTO gifts (name, price, description) VALUES ($1, $2, $3)',
        name, price, description
    )
    await conn.close()

async def delete_gift(gift_id):
    """Удаляет подарок из БД"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('DELETE FROM gifts WHERE id = $1', gift_id)
    await conn.close()

async def update_gift(gift_id, name, price, description):
    """Обновляет подарок в БД"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(
        'UPDATE gifts SET name = $1, price = $2, description = $3 WHERE id = $4',
        name, price, description, gift_id
    )
    await conn.close()

