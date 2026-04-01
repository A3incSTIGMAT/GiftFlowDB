import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID
from database import init_db, update_stats_cache
from handlers import routers
from handlers import admin

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера с FSM storage
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Передаём бота в модуль админки
admin.set_bot(bot)

# Подключаем все роутеры
for router in routers:
    dp.include_router(router)


async def on_startup():
    """Действия при запуске бота"""
    logger.info("🔄 Инициализация базы данных...")
    await init_db()
    
    # Проверка CHANNEL_ID
    from config import CHANNEL_ID
    if CHANNEL_ID:
        logger.info(f"📢 Канал настроен: {CHANNEL_ID}")
        try:
            # Проверяем права бота в канале
            member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=bot.id)
            if member.status in ("administrator", "creator"):
                logger.info("✅ Бот имеет права администратора в канале")
            else:
                logger.warning("⚠️ Бот НЕ является администратором канала!")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось проверить права в канале: {e}")
    else:
        logger.warning("⚠️ CHANNEL_ID не настроен! Посты не будут публиковаться.")
    
    # Обновление кэша статистики
    await update_stats_cache()
    
    logger.info("🚀 Бот запущен! Работаю 24/7!")
    logger.info(f"👑 Супер-админ: {SUPER_ADMIN_ID}")
    logger.info(f"👤 Менеджер: {SUPPORT_ADMIN_ID}")


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 Бот останавливается...")


async def main():
    """Основная функция запуска"""
    await on_startup()
    
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())
