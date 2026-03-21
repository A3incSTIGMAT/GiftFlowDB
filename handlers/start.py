import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import get_main_menu_keyboard, get_back_keyboard
from database import get_user, add_user
from config import ADMIN_IDS, STREAMER_NAME

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    try:
        user = await get_user(message.from_user.id)
        if not user:
            await add_user(message.from_user.id, message.from_user.username)
            logger.info(f"Новый пользователь: {message.from_user.id}")
        else:
            logger.info(f"Существующий пользователь: {message.from_user.id}")
        
        # Проверяем, админ ли пользователь
        if message.from_user.id in ADMIN_IDS:
            from handlers.admin import get_admin_keyboard
            
            await message.answer(
                f"👋 <b>Привет, Админ!</b>\n\n"
                f"Управление ботом {STREAMER_NAME}",
                parse_mode="HTML",
                reply_markup=await get_admin_keyboard(message.from_user.id)
            )
        else:
            await message.answer(
                f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
                f"🎮 Это бот стримерши <b>{STREAMER_NAME}</b>\n\n"
                f"• Подписывайся на соцсети\n"
                f"• Дари подарки — они появятся на стриме\n"
                f"• Вопросы — пиши менеджеру\n\n"
                f"👇 Выбери действие:",
                parse_mode="HTML",
                reply_markup=await get_main_menu_keyboard()
            )
            
        logger.info(f"Команда /start выполнена для {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуй позже.",
            parse_mode="HTML"
        )


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    try:
        # Проверяем, нужно ли обновлять сообщение
        current_text = callback.message.text or ""
        current_markup = callback.message.reply_markup
        
        if callback.from_user.id in ADMIN_IDS:
            from handlers.admin import get_admin_keyboard
            
            # Если уже на админ-панели — не обновляем
            if "Админ-панель" in current_text:
                await callback.answer("🔹 Вы уже в админ-панели")
                return
            
            new_markup = await get_admin_keyboard(callback.from_user.id)
            
            # Проверяем, изменилась ли клавиатура
            if current_markup and str(current_markup) == str(new_markup):
                await callback.answer("🔹 Вы уже в админ-панели")
                return
            
            await callback.message.edit_text(
                "⚙️ <b>Админ-панель</b>",
                parse_mode="HTML",
                reply_markup=new_markup
            )
        else:
            # Если уже в главном меню — не обновляем
            if "Главное меню" in current_text or "Выбери действие" in current_text:
                await callback.answer("🔹 Вы уже в главном меню")
                return
            
            new_markup = await get_main_menu_keyboard()
            
            # Проверяем, изменилась ли клавиатура
            if current_markup and str(current_markup) == str(new_markup):
                await callback.answer("🔹 Вы уже в главном меню")
                return
            
            await callback.message.edit_text(
                "👋 <b>Главное меню</b>",
                parse_mode="HTML",
                reply_markup=new_markup
            )
        
        await callback.answer()
        
    except Exception as e:
        error_str = str(e)
        # Игнорируем ошибку "message is not modified"
        if "message is not modified" in error_str:
            await callback.answer("🔹 Вы уже здесь")
        else:
            logger.error(f"Ошибка в back_to_main: {e}")
            await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(F.data == "contact_support")
async def contact_support(callback: types.CallbackQuery):
    """Связь с поддержкой"""
    try:
        current_text = callback.message.text or ""
        
        # Если уже на странице поддержки — не обновляем
        if "Связь с менеджером" in current_text:
            await callback.answer("🔹 Вы уже в разделе поддержки")
            return
        
        await callback.message.edit_text(
            "💬 <b>Связь с менеджером</b>\n\n"
            "Просто напиши сюда свой вопрос — менеджер ответит в ближайшее время.\n\n"
            "📝 Ты можешь отправить текст, фото или видео",
            parse_mode="HTML",
            reply_markup=await get_back_keyboard()
        )
        await callback.answer()
        
    except Exception as e:
        error_str = str(e)
        if "message is not modified" in error_str:
            await callback.answer("🔹 Вы уже в разделе поддержки")
        else:
            logger.error(f"Ошибка в contact_support: {e}")
            await callback.answer("❌ Ошибка", show_alert=True)


# Тестовая команда для проверки работы бота
@router.message(Command("test"))
async def cmd_test(message: types.Message):
    """Тестовая команда для проверки"""
    try:
        await message.answer(
            "✅ <b>Бот работает!</b>\n\n"
            f"🆔 Твой ID: <code>{message.from_user.id}</code>\n"
            f"👤 Username: @{message.from_user.username or 'нет'}\n"
            f"📛 Имя: {message.from_user.first_name}\n\n"
            f"📊 Статус: {'Админ' if message.from_user.id in ADMIN_IDS else 'Пользователь'}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка в /test: {e}")
        await message.answer("❌ Ошибка при выполнении команды")


# Дополнительная команда для проверки статуса бота
@router.message(Command("status"))
async def cmd_status(message: types.Message):
    """Команда для проверки статуса бота"""
    try:
        from config import DB_PATH
        import os
        
        # Проверяем наличие базы данных
        db_exists = os.path.exists(DB_PATH) if DB_PATH else False
        
        await message.answer(
            "📊 <b>Статус бота</b>\n\n"
            f"✅ Бот активен\n"
            f"📁 База данных: {'✅ существует' if db_exists else '❌ не найдена'}\n"
            f"🗂️ Путь к БД: <code>{DB_PATH}</code>\n"
            f"👑 Режим: {'Админ' if message.from_user.id in ADMIN_IDS else 'Пользователь'}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка в /status: {e}")
        await message.answer("❌ Ошибка при получении статуса")
