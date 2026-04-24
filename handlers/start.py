import logging
from html import escape  # ✅ Для безопасного HTML
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramAPIError

from database import register_user, get_top_heroes, is_admin
from config import SUPER_ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

# ============ ОСНОВНОЕ МЕНЮ ПОЛЬЗОВАТЕЛЯ ============

def get_user_menu_keyboard():
    """Клавиатура основного меню для пользователя"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📺 Twitch"), KeyboardButton(text="📷 Instagram")],
            [KeyboardButton(text="🎁 Каталог подарков"), KeyboardButton(text="🏆 Топ героев")],
            [KeyboardButton(text="❓ О конкурсе"), KeyboardButton(text="🆘 Помощь")]
        ],
        resize_keyboard=True
    )

def get_user_menu_keyboard_with_admin():
    """Клавиатура для админа"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📺 Twitch"), KeyboardButton(text="📷 Instagram")],
            [KeyboardButton(text="🎁 Каталог подарков"), KeyboardButton(text="🏆 Топ героев")],
            [KeyboardButton(text="❓ О конкурсе"), KeyboardButton(text="🆘 Помощь")],
            [KeyboardButton(text="👑 Админ-панель")]
        ],
        resize_keyboard=True
    )

def get_admin_panel_keyboard():
    """Клавиатура админ-панели"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Управление заказами")],
            [KeyboardButton(text="🖼️ Управление галереей")],
            [KeyboardButton(text="✏️ Создать пост"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🏆 Топ героев (админ)"), KeyboardButton(text="➕ Добавить подарок")],
            [KeyboardButton(text="🏠 Главное меню")]
        ],
        resize_keyboard=True
    )

# ============ ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ============

def _safe_username(hero: dict) -> str:
    """Безопасное получение имени пользователя с экранированием"""
    username = hero.get('username')
    if username:
        return escape(username)
    user_id = hero.get('user_id', '?')
    return f"user_{user_id}"


# ============ ОБРАБОТЧИК КОМАНДЫ /start ============

@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """Обработчик команды /start с поддержкой deep links"""
    await state.clear()
    user_id = message.from_user.id
    
    try:
        await register_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации пользователя {user_id}: {e}")
    
    # Проверяем deep link
    args = message.text.split() if message.text else []
    deep_link = args[1] if len(args) > 1 else None
    
    if deep_link == "gifts":
        # ✅ Lazy import с обработкой ошибок
        try:
            from handlers.gifts import show_gifts_catalog
            await show_gifts_catalog(message)
        except ImportError as e:
            logger.error(f"❌ Не удалось импортировать show_gifts_catalog: {e}")
            await message.answer("⚠️ Временная ошибка. Попробуйте позже.")
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
            "❓ Вопросы? Пиши @lanatwitchh"
        )
        keyboard = get_admin_panel_keyboard() if await is_admin(user_id) else get_user_menu_keyboard()
        await message.answer(help_text, parse_mode="HTML", reply_markup=keyboard)
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
    
    keyboard = get_user_menu_keyboard_with_admin() if await is_admin(user_id) else get_user_menu_keyboard()
    await message.answer(
        ("👑 <b>Панель администратора</b>\n\n" if await is_admin(user_id) else "") + welcome_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ============ ОБРАБОТЧИК /cancel ============

@router.message(Command("cancel"))
async def cancel_command(message: types.Message, state: FSMContext):
    """Отмена любого активного действия"""
    await state.clear()
    user_id = message.from_user.id
    
    await message.answer("❌ <b>Действие отменено</b>", parse_mode="HTML")
    
    welcome_text = "🐉 <b>Добро пожаловать!</b>\n\n👇 Выбери действие в меню:"
    keyboard = get_user_menu_keyboard_with_admin() if await is_admin(user_id) else get_user_menu_keyboard()
    
    prefix = "👑 <b>Панель администратора</b>\n\n" if await is_admin(user_id) else ""
    await message.answer(prefix + welcome_text, parse_mode="HTML", reply_markup=keyboard)

# ============ ОБРАБОТКА КНОПОК МЕНЮ ============

@router.message(lambda message: message.text and message.text.strip() == "📺 Twitch")
async def twitch_button(message: types.Message):
    """Кнопка Twitch"""
    await message.answer(
        "📺 <b>Мой Twitch</b>\n\n🔗 https://www.twitch.tv/lanatwitchh",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(lambda message: message.text and message.text.strip() == "📷 Instagram")
async def instagram_button(message: types.Message):
    """Кнопка Instagram"""
    await message.answer(
        "📷 <b>Мой Instagram</b>\n\n🔗 https://www.instagram.com/lanawolfyy",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(lambda message: message.text and message.text.strip() == "🎁 Каталог подарков")
async def catalog_button(message: types.Message, state: FSMContext):
    """Кнопка каталога подарков"""
    await state.clear()
    try:
        from handlers.gifts import show_gifts_catalog
        await show_gifts_catalog(message)
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта каталога: {e}")
        await message.answer("⚠️ Каталог временно недоступен.")

@router.message(lambda message: message.text and message.text.strip() == "🏆 Топ героев")
async def top_heroes_button(message: types.Message, state: FSMContext):
    """Кнопка Топ героев"""
    await state.clear()
    
    try:
        heroes = await get_top_heroes(limit=10)
    except Exception as e:
        logger.error(f"❌ Ошибка получения топа: {e}")
        await message.answer("⚠️ Не удалось загрузить топ героев. Попробуйте позже.")
        return
    
    if not heroes:
        await message.answer("🏆 <b>Топ героев пока пуст</b>\n\nСтань первым!", parse_mode="HTML")
        return
    
    text = "🏆 <b>Топ героев</b>\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    for i, hero in enumerate(heroes, 1):
        medal = medals.get(i, f"{i}.")
        # ✅ Безопасное получение данных + экранирование
        username = _safe_username(hero)
        amount = hero.get('total_amount', 0) or 0
        text += f"{medal} @{username} — {amount:,}₽\n"
    
    text += "\n💎 Топ-1 получит секретный приз!"
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text and message.text.strip() == "❓ О конкурсе")
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
        "Выбери подарок из каталога, оплати и отправь чек."
    )
    await message.answer(contest_text, parse_mode="HTML")

@router.message(lambda message: message.text and message.text.strip() == "🆘 Помощь")
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
        "❓ Вопросы? Пиши @lanatwitchh"
    )
    await message.answer(help_text, parse_mode="HTML")

# ============ ОБРАБОТКА АДМИН-ПАНЕЛИ ============

@router.message(lambda message: message.text and message.text.strip() == "👑 Админ-панель")
async def admin_panel_button(message: types.Message, state: FSMContext):
    """Кнопка Админ-панель"""
    await state.clear()
    user_id = message.from_user.id
    
    if not await is_admin(user_id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    
    admin_text = "👑 <b>Панель администратора</b>\n\nВыберите действие:"
    await message.answer(admin_text, parse_mode="HTML", reply_markup=get_admin_panel_keyboard())

# ============ ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ============

@router.message(lambda message: message.text and message.text.strip() == "🏠 Главное меню")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    user_id = message.from_user.id
    
    welcome_text = "🐉 <b>Добро пожаловать!</b>\n\n👇 Выбери действие в меню:"
    keyboard = get_user_menu_keyboard_with_admin() if await is_admin(user_id) else get_user_menu_keyboard()
    prefix = "👑 <b>Панель администратора</b>\n\n" if await is_admin(user_id) else ""
    
    await message.answer(prefix + welcome_text, parse_mode="HTML", reply_markup=keyboard)

