import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, CHANNEL_ID
from database import init_db, update_stats_cache, get_top_heroes
from handlers import routers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ПОДКЛЮЧАЕМ ВСЕ РОУТЕРЫ
for router in routers:
    dp.include_router(router)


async def set_commands():
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="cancel", description="❌ Отменить действие"),
        BotCommand(command="admin", description="👑 Админ-панель"),
        BotCommand(command="user", description="👤 Пользовательское меню"),
    ]
    await bot.set_my_commands(commands)


async def weekly_top_post():
    """Раз в неделю постим топ героев в канал"""
    while True:
        now = datetime.now()
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 19:
            days_until_sunday = 7
        next_sunday = now + timedelta(days=days_until_sunday)
        next_sunday = next_sunday.replace(hour=19, minute=0, second=0, microsecond=0)
        wait_seconds = (next_sunday - now).total_seconds()
        
        logger.info(f"⏰ Следующий пост топа через {wait_seconds / 3600:.1f} часов")
        await asyncio.sleep(wait_seconds)
        
        try:
            heroes = await get_top_heroes(limit=10)
            
            if not heroes:
                logger.info("Нет героев для поста")
                continue
            
            post_text = "🏆 <b>Топ героев канала за неделю</b>\n\n"
            medals = ["🥇", "🥈", "🥉"]
            
            for i, hero in enumerate(heroes[:10]):
                if i < 3:
                    medal = medals[i]
                else:
                    medal = "🎖️"
                username = hero.get('username') or f"user_{hero['user_id']}"
                post_text += f"{medal} {username} — {hero['total_amount']:,}₽\n"
            
            post_text += "\n💡 <i>Хочешь попасть в топ? Дари подарки через бота!</i>\n"
            post_text += f"👉 @{bot.username}"
            
            await bot.send_message(CHANNEL_ID, post_text, parse_mode="HTML")
            logger.info("✅ Пост топа опубликован")
            
        except Exception as e:
            logger.error(f"Ошибка публикации топа: {e}")


async def on_startup():
    logger.info("🔄 Инициализация базы данных...")
    await init_db()
    await update_stats_cache()
    await set_commands()
    
    if CHANNEL_ID:
        logger.info(f"📢 Канал настроен: {CHANNEL_ID}")
        try:
            member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=bot.id)
            if member.status in ("administrator", "creator"):
                logger.info("✅ Бот имеет права администратора в канале")
            else:
                logger.warning("⚠️ Бот НЕ является администратором канала!")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось проверить права в канале: {e}")
    else:
        logger.warning("⚠️ CHANNEL_ID не настроен!")
    
    if CHANNEL_ID:
        asyncio.create_task(weekly_top_post())
    
    try:
        await bot.send_message(
            SUPER_ADMIN_ID,
            "🤖 <b>Бот запущен!</b>\n\n✅ Все системы работают.\n✅ База данных подключена.\n✅ Обработчики загружены.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось уведомить админа: {e}")
    
    logger.info("🚀 Бот запущен! Работаю 24/7!")
    logger.info(f"👑 Супер-админ: {SUPER_ADMIN_ID}")
    logger.info(f"👤 Менеджер: {SUPPORT_ADMIN_ID}")


async def on_shutdown():
    logger.info("🛑 Бот останавливается...")
    try:
        await bot.send_message(SUPER_ADMIN_ID, "⚠️ <b>Бот остановлен</b>", parse_mode="HTML")
    except:
        pass
    await bot.session.close()
    logger.info("✅ Бот остановлен")


async def main():
    await on_startup()
    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
