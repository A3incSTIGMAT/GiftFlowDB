from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import get_main_menu_keyboard, get_back_keyboard
from database import get_user, add_user
from config import ADMIN_IDS, STREAMER_NAME

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    
    if message.from_user.id in ADMIN_IDS:
        from handlers.admin import get_admin_keyboard
        await message.answer(
            f"👋 <b>Привет, Админ!</b>\n\nУправление ботом {STREAMER_NAME}",
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

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    from handlers.admin import get_admin_keyboard
    if callback.from_user.id in ADMIN_IDS:
        await callback.message.edit_text(
            "⚙️ <b>Админ-панель</b>",
            parse_mode="HTML",
            reply_markup=await get_admin_keyboard(callback.from_user.id)
        )
    else:
        await callback.message.edit_text(
            "👋 <b>Главное меню</b>",
            parse_mode="HTML",
            reply_markup=await get_main_menu_keyboard()
        )
    await callback.answer()

@router.callback_query(F.data == "contact_support")
async def contact_support(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💬 <b>Связь с менеджером</b>\n\n"
        "Просто напиши сюда свой вопрос — менеджер ответит в ближайшее время.",
        parse_mode="HTML",
        reply_markup=await get_back_keyboard()
    )
    await callback.answer()
