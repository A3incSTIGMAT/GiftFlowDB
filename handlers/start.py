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
            await add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
            logger.info(f"Новый пользователь: {message.from_user.id}")
        else:
            logger.info(f"Существующий пользователь: {message.from_user.id}")
        
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
        current_text = callback.message.text or ""
        
        if callback.from_user.id in ADMIN_IDS:
            from handlers.admin import get_admin_keyboard
            
            if "Админ-панель" in current_text:
                await callback.answer("🔹 Вы уже в админ-панели")
                return
            
            await callback.message.edit_text(
                "⚙️ <b>Админ-панель</b>",
                parse_mode="HTML",
                reply_markup=await get_admin_keyboard(callback.from_user.id)
            )
        else:
            if "Главное меню" in current_text or "Выбери действие" in current_text:
                await callback.answer("🔹 Вы уже в главном меню")
                return
            
            await callback.message.edit_text(
                "👋 <b>Главное меню</b>",
                parse_mode="HTML",
                reply_markup=await get_main_menu_keyboard()
            )
        
        await callback.answer()
        
    except Exception as e:
        error_str = str(e)
        if "message is not modified" in error_str:
            await callback.answer("🔹 Вы уже здесь")
        else:
            logger.error(f"Ошибка в back_to_main: {e}")


@router.callback_query(F.data == "contact_support")
async def contact_support(callback: types.CallbackQuery):
    """Связь с поддержкой"""
    try:
        current_text = callback.message.text or ""
        
        if "Связь с менеджером" in current_text:
            await callback.answer("🔹 Вы уже в разделе поддержки")
            return
        
        await callback.message.edit_text(
            "💬 <b>Связь с менеджером</b>\n\n"
            "Просто напиши сюда свой вопрос — менеджер ответит в ближайшее время.",
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
