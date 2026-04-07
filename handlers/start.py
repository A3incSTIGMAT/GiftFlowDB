from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from keyboards import get_main_keyboard, get_admin_keyboard, get_cancel_keyboard
from database import is_admin, is_super_admin

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    if await is_super_admin(user_id):
        keyboard = get_admin_keyboard()
        await message.answer(
            "👑 <b>Добро пожаловать в админ-панель!</b>\n\n"
            "Вы вошли как супер-админ. Вам доступно полное управление ботом.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    elif await is_admin(user_id):
        keyboard = get_admin_keyboard()
        await message.answer(
            "🛠️ <b>Панель менеджера</b>\n\n"
            "Вам доступно управление заказами и галереей.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        keyboard = get_main_keyboard()
        await message.answer(
            "🎁 <b>Добро пожаловать в GiftFlow!</b>\n\n"
            "Здесь ты можешь выбрать подарок для Ланы и попасть в топ героев канала.\n\n"
            "⬇️ <i>Используй кнопки меню для навигации</i>",
            parse_mode="HTML",
            reply_markup=keyboard
        )

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Быстрый вход в админку"""
    user_id = message.from_user.id
    
    if await is_super_admin(user_id) or await is_admin(user_id):
        keyboard = get_admin_keyboard()
        await message.answer(
            "🛠️ <b>Админ-панель</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await message.answer("❌ У вас нет доступа к админ-панели.")

@router.message(Command("user"))
async def cmd_user(message: types.Message):
    """Переключение в пользовательское меню"""
    keyboard = get_main_keyboard()
    await message.answer(
        "🎁 <b>Главное меню</b>\n\n"
        "Выберите подарок или посмотрите топ героев:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.message(Command("channel_id"))
async def cmd_channel_id(message: types.Message):
    """Узнать ID канала (только для админов)"""
    user_id = message.from_user.id
    
    if await is_super_admin(user_id) or await is_admin(user_id):
        await message.answer(
            f"📢 <b>ID этого чата:</b>\n"
            f"<code>{message.chat.id}</code>\n\n"
            f"Используйте это значение в CHANNEL_ID",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Команда только для администраторов.")

@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отмена текущего действия"""
    await state.clear()
    user_id = message.from_user.id
    
    if await is_super_admin(user_id) or await is_admin(user_id):
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_keyboard())
    else:
        await message.answer("❌ Действие отменено.", reply_markup=get_main_keyboard())

@router.message(lambda message: message.text == "Главное меню")
async def back_to_main(message: types.Message):
    """Возврат в главное меню (для обычных пользователей)"""
    keyboard = get_main_keyboard()
    await message.answer(
        "🎁 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.message(lambda message: message.text == "🎁 Главное меню")
async def back_from_admin_to_user(message: types.Message):
    """Возврат из админ-панели в пользовательское меню"""
    keyboard = get_main_keyboard()
    await message.answer(
        "🎁 <b>Возврат в главное меню</b>\n\n"
        "Вы переключились в режим пользователя:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@router.message(lambda message: message.text == "👑 Админ-панель")
async def admin_panel_button(message: types.Message):
    """Кнопка админ-панели в пользовательском меню"""
    user_id = message.from_user.id
    
    if await is_super_admin(user_id) or await is_admin(user_id):
        keyboard = get_admin_keyboard()
        await message.answer(
            "🛠️ <b>Админ-панель</b>\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await message.answer(
            "❌ У вас нет доступа к админ-панели.\n\n"
            "Вернитесь в главное меню:",
            reply_markup=get_main_keyboard()
        )
