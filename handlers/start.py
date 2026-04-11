import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from database import register_user, get_top_heroes
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

def get_user_menu_keyboard_with_admin():
    """Клавиатура основного меню для админа (с кнопкой админ-панели)"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📺 Twitch"), KeyboardButton(text="📷 Instagram")],
            [KeyboardButton(text="🎁 Каталог подарков"), KeyboardButton(text="🏆 Топ героев")],
            [KeyboardButton(text="❓ О конкурсе"), KeyboardButton(text="🆘 Помощь")],
            [KeyboardButton(text="👑 Админ-панель")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_panel_keyboard():
    """Клавиатура админ-панели"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Управление заказами")],
            [KeyboardButton(text="🖼️ Управление галереей")],
            [KeyboardButton(text="✏️ Создать пост"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🏆 Топ героев (админ)"), KeyboardButton(text="➕ Добавить подарок")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard

# ============ ОБРАБОТЧИК КОМАНДЫ /start ============

@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """Обработчик команды /start с поддержкой deep links"""
    
    await state.clear()
    user_id = message.from_user.id
    
    # Регистрируем пользователя (синхронная функция)
    register_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Проверяем deep link
    args = message.text.split()
    deep_link = args[1] if len(args) > 1 else None
    
    if deep_link == "gifts":
        from handlers.gifts import show_gifts_catalog
        await show_gifts_catalog(message)
        return
    
    elif deep_link == "help":
        help_text = "🆘 <b>Помощь</b>\n\n📌 Как сделать подарок?\n1. Выбери подарок\n2. Оплати по ссылке\n3. Отправь чек"
        kb = get_admin_panel_keyboard() if user_id == SUPER_ADMIN_ID else get_user_menu_keyboard()
        await message.answer(help_text, parse_mode="HTML", reply_markup=kb)
        return
    
    # Обычный /start
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
            reply_markup=get_user_menu_keyboard_with_admin()
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
    await state.clear()
    user_id = message.from_user.id
    await message.answer("❌ Действие отменено", parse_mode="HTML")
    
    welcome_text = "🐉 <b>Добро пожаловать!</b>\n\n👇 Выбери действие в меню:"
    
    if user_id == SUPER_ADMIN_ID:
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_user_menu_keyboard_with_admin())
    else:
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_user_menu_keyboard())

# ============ ОБРАБОТКА КНОПОК МЕНЮ ============

@router.message(lambda message: message.text == "📺 Twitch")
async def twitch_button(message: types.Message):
    await message.answer("📺 Twitch: https://www.twitch.tv/lanatwitchh", disable_web_page_preview=True)

@router.message(lambda message: message.text == "📷 Instagram")
async def instagram_button(message: types.Message):
    await message.answer("📷 Instagram: https://www.instagram.com/lanawolfyy", disable_web_page_preview=True)

@router.message(lambda message: message.text == "🎁 Каталог подарков")
async def catalog_button(message: types.Message, state: FSMContext):
    await state.clear()
    from handlers.gifts import show_gifts_catalog
    await show_gifts_catalog(message)

@router.message(lambda message: message.text == "🏆 Топ героев")
async def top_heroes_button(message: types.Message, state: FSMContext):
    await state.clear()
    heroes = get_top_heroes(limit=10)
    
    if not heroes:
        await message.answer("🏆 Топ героев пока пуст", parse_mode="HTML")
        return
    
    text = "🏆 <b>Топ героев</b>\n\n"
    for i, hero in enumerate(heroes, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        username = hero.get('username') or f"user_{hero['user_id']}"
        text += f"{medal} @{username} — {hero['total_amount']:,}₽\n"
    text += "\n💎 Топ-1 получит секретный приз!"
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text == "❓ О конкурсе")
async def about_contest_button(message: types.Message, state: FSMContext):
    await state.clear()
    text = "❓ <b>О конкурсе</b>\n\n🏆 Призы:\n• Топ-1: Секретный приз\n• Топ-3: Упоминание\n• Все участники: Имя в Топе"
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text == "🆘 Помощь")
async def help_button(message: types.Message, state: FSMContext):
    await state.clear()
    text = "🆘 <b>Помощь</b>\n\n1. Выбери подарок\n2. Оплати по ссылке\n3. Отправь чек"
    await message.answer(text, parse_mode="HTML")

# ============ ОБРАБОТКА АДМИН-ПАНЕЛИ ============

@router.message(lambda message: message.text == "👑 Админ-панель")
async def admin_panel_button(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    if user_id != SUPER_ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    
    admin_text = "👑 <b>Панель администратора</b>\n\nВыберите действие:"
    await message.answer(admin_text, parse_mode="HTML", reply_markup=get_admin_panel_keyboard())

# ============ ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ============

@router.message(lambda message: message.text == "🏠 Главное меню")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    welcome_text = "🐉 <b>Добро пожаловать!</b>\n\n👇 Выбери действие в меню:"
    
    if user_id == SUPER_ADMIN_ID:
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_user_menu_keyboard_with_admin())
    else:
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=get_user_menu_keyboard())
