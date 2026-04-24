import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from database import register_user, get_top_heroes, is_admin
from config import SUPER_ADMIN_ID, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

# ============ ОСНОВНОЕ МЕНЮ ПОЛЬЗОВАТЕЛЯ ============

def get_user_menu_keyboard():
    """Клавиатура основного меню для обычного пользователя"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📺 Twitch"), KeyboardButton(text="📷 Instagram")],
            [KeyboardButton(text="🎁 Каталог подарков"), KeyboardButton(text="🏆 Топ героев")],
            [KeyboardButton(text="❓ О конкурсе"), KeyboardButton(text="🆘 Помощь")]
        ],
        resize_keyboard=True
    )

def get_user_menu_keyboard_with_admin():
    """Клавиатура основного меню для админа (с кнопкой админ-панели)"""
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

# ============ ОБРАБОТЧИК КОМАНДЫ /start ============

@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    await state.clear()
    
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    last_name = message.from_user.last_name
    
    # Регистрируем пользователя
    try:
        await register_user(user_id, username, first_name, last_name)
    except Exception as e:
        logger.error(f"Ошибка регистрации: {e}")
    
    welcome_text = (
        "🐉 <b>Добро пожаловать!</b>\n\n"
        "Это бот для подарков.\n\n"
        "💎 <b>Что здесь есть:</b>\n"
        "• Подарки от 10₽ до 150 000₽\n"
        "• Топ героев\n"
        "• Секретный приз для победителя\n\n"
        "👇 Выбери действие в меню:"
    )
    
    # Проверяем, админ ли пользователь
    admin_check = await is_admin(user_id)
    
    if admin_check:
        await message.answer(
            "👑 <b>Панель администратора</b>\n\n" + welcome_text,
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
    """Отмена любого активного действия"""
    await state.clear()
    user_id = message.from_user.id
    
    await message.answer("❌ <b>Действие отменено</b>", parse_mode="HTML")
    
    welcome_text = "🐉 <b>Добро пожаловать!</b>\n\n👇 Выбери действие в меню:"
    admin_check = await is_admin(user_id)
    
    if admin_check:
        await message.answer(
            "👑 <b>Панель администратора</b>\n\n" + welcome_text,
            parse_mode="HTML",
            reply_markup=get_user_menu_keyboard_with_admin()
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
        "📺 <b>Мой Twitch</b>\n\n🔗 https://www.twitch.tv/lanatwitchh",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(lambda message: message.text == "📷 Instagram")
async def instagram_button(message: types.Message):
    """Кнопка Instagram"""
    await message.answer(
        "📷 <b>Мой Instagram</b>\n\n🔗 https://www.instagram.com/lanawolfyy",
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
    
    try:
        heroes = await get_top_heroes(limit=10)
    except Exception as e:
        logger.error(f"Ошибка получения топа: {e}")
        await message.answer("⚠️ Не удалось загрузить топ героев. Попробуйте позже.")
        return
    
    if not heroes:
        await message.answer("🏆 <b>Топ героев пока пуст</b>\n\nСтань первым!", parse_mode="HTML")
        return
    
    text = "🏆 <b>Топ героев</b>\n\n"
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    for i, hero in enumerate(heroes, 1):
        medal = medals.get(i, f"{i}.")
        username = hero.get('username') or f"user_{hero['user_id']}"
        amount = hero.get('total_amount', 0)
        text += f"{medal} @{username} — {amount:,}₽\n"
    
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
        "Выбери подарок из каталога, оплати и отправь чек."
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
        "❓ Вопросы? Пиши @lanatwitchh"
    )
    await message.answer(help_text, parse_mode="HTML")

# ============ ОБРАБОТКА АДМИН-ПАНЕЛИ ============

@router.message(lambda message: message.text == "👑 Админ-панель")
async def admin_panel_button(message: types.Message, state: FSMContext):
    """Кнопка Админ-панель"""
    await state.clear()
    user_id = message.from_user.id
    
    admin_check = await is_admin(user_id)
    
    if not admin_check:
        await message.answer(
            "⛔ <b>У вас нет доступа к админ-панели!</b>\n\n"
            "Эта панель доступна только администраторам.",
            parse_mode="HTML"
        )
        return
    
    admin_text = (
        "👑 <b>Панель администратора</b>\n\n"
        "Доступные действия:\n\n"
        "📦 Управление заказами — подтверждение/отклонение\n"
        "🖼️ Управление галереей — добавление/удаление фото\n"
        "✏️ Создать пост — публикация в канал\n"
        "📊 Статистика — просмотр данных\n"
        "🏆 Топ героев (админ) — просмотр топа\n"
        "➕ Добавить подарок — новый подарок в каталог\n\n"
        "👇 Выберите действие:"
    )
    
    await message.answer(
        admin_text,
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )

# ============ ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ============

@router.message(lambda message: message.text == "🏠 Главное меню")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    """Возврат в главное меню из админ-панели"""
    await state.clear()
    user_id = message.from_user.id
    
    welcome_text = "🐉 <b>Добро пожаловать!</b>\n\n👇 Выбери действие в меню:"
    admin_check = await is_admin(user_id)
    
    if admin_check:
        await message.answer(
            "👑 <b>Панель администратора</b>\n\n" + welcome_text,
            parse_mode="HTML",
            reply_markup=get_user_menu_keyboard_with_admin()
        )
    else:
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_user_menu_keyboard()
        )
