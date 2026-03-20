import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from config import BOT_TOKEN, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, ADMIN_IDS
from database import init_db
from handlers import routers

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключаем все роутеры
for router in routers:
    dp.include_router(router)

# Глобальный хендлер для неизвестных команд
@dp.message(Command("start"))
async def dummy_start(message: Message):
    # Этот хендлер уже есть в start.py, но оставляем на всякий случай
    pass

@dp.message()
async def handle_unknown(message: Message):
    if message.from_user.id in ADMIN_IDS:
        return
    
    # Пересылаем сообщение менеджеру
    await message.forward(SUPPORT_ADMIN_ID)
    await message.answer(
        "✅ Сообщение отправлено менеджеру! Я отвечу в ближайшее время.",
        parse_mode="HTML"
    )

async def main():
    logger.info("🔄 Инициализация базы данных...")
    await init_db()
    
    logger.info("🚀 Бот запущен! Работаю 24/7!")
    logger.info(f"👑 Супер-админ: {SUPER_ADMIN_ID}")
    logger.info(f"👤 Менеджер: {SUPPORT_ADMIN_ID}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
