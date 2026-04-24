import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
# ✅ Исправленный импорт для aiogram 3.x
from aiogram.exceptions import TelegramForbiddenError, TelegramAPIError

from config import BOT_TOKEN, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, CHANNEL_ID
from database import init_db, update_stats_cache, get_top_heroes
from handlers import routers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ПОДКЛЮЧАЕМ ВСЕ РОУТЕРЫ
for router in routers:
    dp.include_router(router)


async def set_commands():
    """Установка команд бота"""
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
                medal = medals[i] if i < 3 else "🎖️"
                # ✅ Безопасное получение данных с дефолтами
                username = hero.get('username') or f"user_{hero.get('user_id', '?')}"
                amount = hero.get('total_amount', 0) or 0
                post_text += f"{medal} {username} — {amount:,}₽\n"
            
            post_text += "\n💡 <i>Хочешь попасть в топ? Дари подарки через бота!</i>\n"
            bot_info = await bot.get_me()
            post_text += f"👉 @{bot_info.username}"
            
            await bot.send_message(CHANNEL_ID, post_text, parse_mode="HTML")
            logger.info("✅ Пост топа опубликован")
            
        except TelegramForbiddenError:
            logger.error("❌ Бот не имеет прав на отправку в канал (403 Forbidden)")
        except TelegramAPIError as e:
            logger.error(f"❌ Ошибка Telegram API при публикации топа: {e}")
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка публикации топа: {type(e).__name__}: {e}", exc_info=True)


async def on_startup():
    """Инициализация при запуске бота"""
    logger.info("🔄 Инициализация базы данных...")
    await init_db()
    
    # ✅ Если кэш не используется — можно закомментировать
    # _ = await update_stats_cache()
    
    await set_commands()
    
    # ✅ Кэшируем info о боте для безопасного использования
    bot_info = await bot.get_me()
    logger.info(f"🤖 Бот: @{bot_info.username} (ID: {bot_info.id})")
    
    if CHANNEL_ID:
        logger.info(f"📢 Канал настроен: {CHANNEL_ID}")
        try:
            member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=bot_info.id)
            if member.status in ("administrator", "creator"):
                logger.info("✅ Бот имеет права администратора в канале")
            else:
                logger.warning("⚠️ Бот НЕ является администратором канала!")
        except TelegramForbiddenError:
            logger.error("❌ Бот не добавлен в канал или не имеет прав (403)")
        except TelegramAPIError as e:
            logger.warning(f"⚠️ Не удалось проверить права в канале: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Неожиданная ошибка проверки канала: {type(e).__name__}: {e}")
    else:
        logger.warning("⚠️ CHANNEL_ID не настроен!")
    
    if CHANNEL_ID:
        asyncio.create_task(weekly_top_post())
        logger.info("📅 Запущена задача еженедельной публикации топа")
    
    # ✅ Уведомление админа с обработкой ошибок
    try:
        await bot.send_message(
            SUPER_ADMIN_ID,
            "🤖 <b>Бот запущен!</b>\n\n✅ Все системы работают.\n✅ База данных подключена.\n✅ Обработчики загружены.",
            parse_mode="HTML"
        )
    except TelegramForbiddenError:
        logger.warning("⚠️ Админ заблокировал бота или не начал диалог (403)")
    except TelegramAPIError as e:
        logger.warning(f"⚠️ Ошибка отправки уведомления админу: {e}")
    except Exception as e:
        logger.warning(f"⚠️ Неожиданная ошибка уведомления: {type(e).__name__}: {e}")
    
    logger.info("🚀 Бот запущен! Работаю 24/7!")
    logger.info(f"👑 Супер-админ: {SUPER_ADMIN_ID}")
    logger.info(f"👤 Менеджер: {SUPPORT_ADMIN_ID}")


async def on_shutdown():
    """Очистка при остановке бота"""
    logger.info("🛑 Бот останавливается...")
    try:
        await bot.send_message(SUPER_ADMIN_ID, "⚠️ <b>Бот остановлен</b>", parse_mode="HTML")
    except TelegramForbiddenError:
        pass  # Админ заблокировал бота
    except TelegramAPIError:
        pass
    except Exception:
        pass
    
    # ✅ В aiogram 3 сессией управляет Dispatcher — не закрываем вручную
    logger.info("✅ Бот остановлен")


async def main():
    """Точка входа"""
    await on_startup()
    try:
        # ✅ allowed_updates можно не указывать — aiogram сам определит
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("👋 Получен сигнал остановки (Ctrl+C)")
    except TelegramAPIError as e:
        logger.critical(f"❌ Критическая ошибка Telegram API: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка: {type(e).__name__}: {e}", exc_info=True)
        raise
    finally:
        await on_shutdown()


if __name__ == "__main__":
    asyncio.run(main())

