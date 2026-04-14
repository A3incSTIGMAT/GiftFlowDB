import logging
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from database import register_user, get_top_heroes, get_goal_progress
from config import SUPER_ADMIN_ID, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

# ============ ФУНКЦИЯ ПРОВЕРКИ АДМИНА ============

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом (супер-админ или админ поддержки)"""
    return user_id == SUPER_ADMIN_ID or user_id == SUPPORT_ADMIN_ID

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
    
    # Регистрируем пользователя (синхронная функция - БЕЗ await)
    register_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Проверяем deep link (то, что после /start)
    args = message.text.split()
    deep_link = args[1] if len(args) > 1 else None
    
    if deep_link == "gifts":
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
        
        if is_admin(user_id):
            await message.answer(help_text, parse_mode="HTML", reply_markup=get_admin_panel_keyboard())
        else:
            await message.answer(help_text, parse_mode="HTML", reply_markup=get_user_menu_keyboard())
        return
    
    # Получаем прогресс цели
    progress = get_goal_progress()
    
    # Формируем индикатор цели
    goal_text = f"""
🎯 <b>ТЕКУЩИЙ СБОР: {progress['name']}</b>
💰 Собрано: {progress['collected']:,}₽ из {progress['target']:,}₽ ({progress['percent']}%)

{progress['bars']} {progress['percent']}%

💫 До цели: {progress['remaining']:,}₽
"""
    
    # Обычный /start
    welcome_text = (
        "🐉 <b>Добро пожаловать!</b>\n\n"
        "Это бот для подарков.\n\n"
        "💎 <b>Что здесь есть:</b>\n"
        "• Подарки от 10₽ до 150 000₽\n"
        "• Топ героев\n"
        "• Секретный приз для победителя\n\n"
    )
    
    full_text = welcome_text + goal_text + "\n👇 Выбери действие в меню:"
    
    if is_admin(user_id):
        await message.answer(
            "👑 <b>Панель администратора</b>\n\n" + full_text,
            parse_mode="HTML",
            reply_markup=get_user_menu_keyboard_with_admin()
        )
    else:
        await message.answer(
            full_text,
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
    
    # Получаем прогресс цели
    progress = get_goal_progress()
    
    goal_text = f"""
🎯 <b>ТЕКУЩИЙ СБОР: {progress['name']}</b>
💰 Собрано: {progress['collected']:,}₽ из {progress['target']:,}₽ ({progress['percent']}%)

{progress['bars']} {progress['percent']}%

💫 До цели: {progress['remaining']:,}₽
"""
    
    welcome_text = "🐉 <b>Добро пожаловать!</b>\n\n👇 Выбери действие в меню:\n\n" + goal_text
    
    if is_admin(user_id):
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
    
    heroes = get_top_heroes(limit=10)
    
    if not heroes:
        await message.answer("🏆 <b>Топ героев пока пуст</b>\n\nСтань первым!", parse_mode="HTML")
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
    
    if not is_admin(user_id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    
    admin_text = "👑 <b>Панель администратора</b>\n\nВыберите действие:"
    
    await message.answer(
        admin_text,
        parse_mode="HTML",
        reply_markup=get_admin_panel_keyboard()
    )

# ============ ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ============

@router.message(lambda message: message.text == "🏠 Главное меню")
async def back_to_main_menu(message: types.Message, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    user_id = message.from_user.id
    
    # Получаем прогресс цели
    progress = get_goal_progress()
    
    goal_text = f"""
🎯 <b>ТЕКУЩИЙ СБОР: {progress['name']}</b>
💰 Собрано: {progress['collected']:,}₽ из {progress['target']:,}₽ ({progress['percent']}%)

{progress['bars']} {progress['percent']}%

💫 До цели: {progress['remaining']:,}₽
"""
    
    welcome_text = "🐉 <b>Добро пожаловать!</b>\n\n👇 Выбери действие в меню:\n\n" + goal_text
    
    if is_admin(user_id):
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
