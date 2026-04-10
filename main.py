import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, CHANNEL_ID
from database import init_db, update_stats_cache, get_top_heroes
from handlers import routers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Регистрируем все роутеры
for router in routers:
    dp.include_router(router)


async def set_commands():
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота"),
        BotCommand(command="cancel", description="❌ Отменить действие"),
        BotCommand(command="help", description="🆘 Помощь"),
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
            heroes = get_top_heroes(limit=10)  # <-- УБРАЛ await, функция синхронная
            
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
                post_text += f"{medal} {username} — {hero['total_amount']}₽\n"
            
            post_text += "\n💡 <i>Хочешь попасть в топ? Дари подарки через бота!</i>\n"
            post_text += f"👉 @{bot.username}"
            
            await bot.send_message(CHANNEL_ID, post_text, parse_mode="HTML")
            logger.info("✅ Пост топа опубликован")
            
        except Exception as e:
            logger.error(f"Ошибка публикации топа: {e}")


async def on_startup():
    """Действия при запуске бота"""
    logger.info("🔄 Инициализация базы данных...")
    
    # init_db - синхронная функция, НЕ используем await
    init_db()
    logger.info("✅ База данных готова")
    
    # update_stats_cache - синхронная функция
    update_stats_cache()
    
    # Устанавливаем команды бота
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
        logger.warning("⚠️ CHANNEL_ID не настроен! Посты не будут публиковаться.")
    
    # Запускаем фоновую задачу для топа (только если есть канал)
    if CHANNEL_ID:
        asyncio.create_task(weekly_top_post())
    
    # Уведомляем админа о запуске
    try:
        await bot.send_message(
            SUPER_ADMIN_ID,
            "🤖 <b>Бот запущен!</b>\n\n"
            "✅ Все системы работают.\n"
            "✅ База данных подключена.\n"
            "✅ Обработчики загружены.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось уведомить админа: {e}")
    
    logger.info("🚀 Бот запущен! Работаю 24/7!")
    logger.info(f"👑 Супер-админ: {SUPER_ADMIN_ID}")
    logger.info(f"👤 Менеджер: {SUPPORT_ADMIN_ID}")


async def on_shutdown():
    """Действия при остановке бота"""
    logger.info("🛑 Бот останавливается...")
    
    try:
        await bot.send_message(
            SUPER_ADMIN_ID,
            "⚠️ <b>Бот остановлен</b>\n\nБот завершает свою работу."
        )
    except:
        pass
    
    await bot.session.close()
    logger.info("✅ Бот остановлен")


async def main():
    """Основная функция запуска"""
    await on_startup()
    
    try:
        logger.info("🔄 Начинаем polling...")
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    except Exception as e:
        logger.error(f"❌ Ошибка при работе бота: {e}")
        raise
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
