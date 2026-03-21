import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, ADMIN_IDS
from database import init_db
from handlers import routers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

for router in routers:
    dp.include_router(router)

# ========== УНИВЕРСАЛЬНЫЙ ХЕНДЛЕР ДЛЯ ТЕСТА ==========
@dp.message()
async def echo_all(message: Message):
    """Универсальный обработчик для любых сообщений"""
    await message.answer(f"✅ Получил твоё сообщение: {message.text}")
    print(f"Получено: {message.text}")
# ====================================================

async def main():
    logger.info("🔄 Инициализация базы данных...")
    await init_db()
    
    logger.info("🚀 Бот запущен! Работаю 24/7!")
    logger.info(f"👑 Супер-админ: {SUPER_ADMIN_ID}")
    logger.info(f"👤 Менеджер: {SUPPORT_ADMIN_ID}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
