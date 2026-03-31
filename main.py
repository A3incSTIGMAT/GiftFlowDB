import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID
from database import init_db
from handlers import routers
from handlers import ozon_payments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Передаём бота в модуль Озон
ozon_payments.set_bot(bot)

# Подключаем все роутеры
for router in routers:
    dp.include_router(router)

async def main():
    logger.info("🔄 Инициализация базы данных...")
    await init_db()
    
    logger.info("🚀 Бот запущен! Работаю 24/7!")
    logger.info(f"👑 Супер-админ: {SUPER_ADMIN_ID}")
    logger.info(f"👤 Менеджер: {SUPPORT_ADMIN_ID}")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
