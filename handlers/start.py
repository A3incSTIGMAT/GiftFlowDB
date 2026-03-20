from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import get_main_menu_keyboard
from database import get_user, add_user

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username)
    
    await message.answer(
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"🎮 Это бот стримерши <b>Ланы</b>\n\n"
        f"• Подписывайся на соцсети\n"
        f"• Дари подарки — они появятся на стриме\n"
        f"• Вопросы — пиши менеджеру\n\n"
        f"👇 Выбери действие:",
        parse_mode="HTML",
        reply_markup=await get_main_menu_keyboard()
    )
