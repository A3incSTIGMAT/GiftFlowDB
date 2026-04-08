import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from database import register_user
from keyboards import get_admin_keyboard
from config import SUPER_ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

# ============ ОСНОВНОЕ МЕНЮ ПОЛЬЗОВАТЕЛЯ ============

def get_user_menu_keyboard():
    """Клавиатура основного меню для пользователя"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📺 Twitch"), KeyboardButton(text="📷 Instagram")],
            [KeyboardButton(text="🎁 Каталог подарков"), KeyboardButton(text="🏆 Топ героев")],
            [KeyboardButton(text="❓ О конкурсе"), KeyboardButton(text="🆘 Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard

# ============ ОБРАБОТЧИК КОМАНДЫ /start ============

@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """Обработчик команды /start с поддержкой deep links"""
    
    # Принудительно очищаем состояние
    await state.clear()
    
    user_id = message.from_user.id
    
    # Регистрируем пользователя
    await register_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Проверяем deep link (то, что после /start)
    args = message.text.split()
    deep_link = None
    if len(args) > 1:
        deep_link = args[1]
    
    # Обработка deep links из канала
    if deep_link == "gifts":
        # Показываем каталог подарков
        from handlers.gifts import show_gifts_catalog
        await show_gifts_catalog(message)
        return
    
    elif deep_link == "help":
        help_text = (
            "🆘 <b>Помощь</b>\n\n"
            "📌 <b>Как сделать подарок?</b>\n"
            "1. Выбери подарок в «Каталог подарков»\n"
            "2. Нажми «Оплатить»\n"
            "3. Оплати по ссылке\n"
            "4. Отправь скриншот чека сюда\n"
            "5. Я подтвержу подарок\n\n"
            "📌 <b>Что даёт подарок?</b>\n"
            "• Имя в Топе героев\n"
            "• Шанс на секретный приз\n\n"
            "❓ Вопросы? Пиши @lanatwitchh"
        )
        
        if user_id == SUPER_ADMIN_ID:
            await message.answer(help_text, parse_mode="HTML", reply_markup=get_admin_keyboard())
        else:
            await message.answer(help_text, parse_mode="HTML", reply_markup=get_user_menu_keyboard())
        return
    
    # Обычный /start без параметров
    welcome_text = (
        "🐉 <b>Добро пожаловать!</b>\n\n"
        "Это бот для подарков.\n\n"
        "💎 <b>Что здесь есть:</b>\n"
        "• Подарки от 10₽ до 150 000₽\n"
        "• Топ героев\n"
        "• Секретный приз для победителя\n\n"
        "👇 Выбери действие в меню:"
    )
    
    if user_id == SUPER_ADMIN_ID:
        await message.answer(
            "👑 <b>Супер-админ</b>\n\n" + welcome_text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_user_menu_keyboard()
        )

# ============ ОБРАБОТЧИК /cancel ============

@router.message(Command("cancel"))
async def cancel_command(message: types.Message, state: FSMContext):
    """Отмена любого активного действия"""
    await state.clear()
    user_id = message.from_user.id
    
    await message.answer(
        "❌ <b>Действие отменено</b>",
        parse_mode="HTML"
    )
    
    welcome_text = (
        "🐉 <b>Добро пожаловать!</b>\n\n"
        "👇 Выбери действие в меню:"
    )
    
    if user_id == SUPER_ADMIN_ID:
        await message.answer(
            "👑 <b>Супер-админ</b>\n\n" + welcome_text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_user_menu_keyboard()
        )

# ============ ОБРАБОТКА КНОПОК МЕНЮ ============

@router.message(lambda message: message.text == "📺 Twitch")
async def twitch_button(message: types.Message):
    """Кнопка Twitch"""
    await message.answer(
        "📺 <b>Мой Twitch</b>\n\n"
        "🔗 https://www.twitch.tv/lanatwitchh",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(lambda message: message.text == "📷 Instagram")
async def instagram_button(message: types.Message):
    """Кнопка Instagram"""
    await message.answer(
        "📷 <b>Мой Instagram</b>\n\n"
        "🔗 https://www.instagram.com/lanawolfyy",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(lambda message: message.text == "🎁 Каталог подарков")
async def catalog_button(message: types.Message, state: FSMContext):
    """Кнопка каталога подарков"""
    await state.clear()
    from handlers.gifts import show_gifts_catalog
    await show_gifts_catalog(message)

@router.message(lambda message: message.text == "🏆 Топ героев")
async def top_heroes_button(message: types.Message, state: FSMContext):
    """Кнопка Топ героев"""
    await state.clear()
    from database import get_top_heroes
    
    heroes = await get_top_heroes(limit=10)
    
    if not heroes:
        await message.answer(
            "🏆 <b>Топ героев пока пуст</b>\n\n"
            "Стань первым! Выбери подарок из каталога.",
            parse_mode="HTML"
        )
        return
    
    text = "🏆 <b>Топ героев</b>\n\n"
    for i, hero in enumerate(heroes, 1):
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        medal = medals.get(i, f"{i}.")
        username = hero.get('username') or f"user_{hero['user_id']}"
        text += f"{medal} @{username} — {hero['total_amount']:,}₽\n"
    
    text += "\n💎 Топ-1 получит секретный приз!"
    
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text == "❓ О конкурсе")
async def about_contest_button(message: types.Message, state: FSMContext):
    """Кнопка О конкурсе"""
    await state.clear()
    contest_text = (
        "❓ <b>О конкурсе</b>\n\n"
        "🏆 <b>Призы:</b>\n"
        "• Топ-1: Секретный приз\n"
        "• Топ-3: Упоминание в посте\n"
        "• Все участники: Имя в Топе героев\n\n"
        "💎 <b>Как участвовать?</b>\n"
        "Выбери подарок из каталога, оплати и отправь чек.\n\n"
        "📊 <b>Топ обновляется</b> после каждого подтверждённого подарка."
    )
    
    await message.answer(contest_text, parse_mode="HTML")

@router.message(lambda message: message.text == "🆘 Помощь")
async def help_button(message: types.Message, state: FSMContext):
    """Кнопка Помощь"""
    await state.clear()
    help_text = (
        "🆘 <b>Помощь</b>\n\n"
        "📌 <b>Как сделать подарок?</b>\n"
        "1. Выбери подарок в «Каталог подарков»\n"
        "2. Нажми «Оплатить»\n"
        "3. Оплати по ссылке\n"
        "4. Отправь скриншот чека сюда\n"
        "5. Я подтвержу подарок\n\n"
        "📌 <b>Что даёт подарок?</b>\n"
        "• Имя в Топе героев\n"
        "• Шанс на секретный приз\n\n"
        "❓ Вопросы? Пиши @lanatwitchh"
    )
    
    await message.answer(help_text, parse_mode="HTML")

# ============ ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ============

@router.message(lambda message: message.text == "🏠 Главное меню")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    """Возврат в главное меню из админки"""
    await state.clear()
    user_id = message.from_user.id
    
    welcome_text = (
        "🐉 <b>Добро пожаловать!</b>\n\n"
        "👇 Выбери действие в меню:"
    )
    
    if user_id == SUPER_ADMIN_ID:
        await message.answer(
            "👑 <b>Супер-админ</b>\n\n" + welcome_text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_user_menu_keyboard()
        )
