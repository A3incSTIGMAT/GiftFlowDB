import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import init_db, get_user, add_user, get_all_gifts, add_transaction, get_all_transactions, clear_transactions
from keep_alive import keep_alive

# ==================== КОНФИГ ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')
SUPER_ADMIN_ID = 895844198  # Полный доступ (Я)
SUPPORT_ADMIN_ID = 7076299389  # Связь с клиентами и оплаты (Лана)
ADMIN_IDS = [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]

# РАСПРЕДЕЛЕНИЕ ПРИБЫЛИ (от комиссии 10%)
FEE_PERCENT = 0.10  # Комиссия 10% от суммы
PROFIT_SPLIT = {
    'lana': 0.47,        # 47% Лана
    'admin': 0.28,       # 28% Я (Супер-админ)
    'development': 0.19, # 19% Развитие проекта
    'tax': 0.06          # 6% Налог
}

# ТВОИ РЕКВИЗИТЫ
PAYMENT_DETAILS = """
💳 <b>Реквизиты для оплаты:</b>

📱 <b>СБП (Система Быстрых Платежей):</b>
   Номер: +7 995 253-89-15
   Банк: Озон Банк
   Получатель: Александр Б.

💳 <b>Банковская карта:</b>
   Номер: 2200 1520 5573 6857
   Банк: Альфа-Банк Бизнес
   Получатель: Александр Б.

₮ <b>USDT (TRC20):</b>
   Адрес: THYyPKBfbHiZaxjj3wFE8SXRXvF3WN6scw
   Сеть: TRON (TRC20)

⚠️ <b>ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ:</b>
❗ Перевод на карту другого банка (не Альфа-Банк) может привести к ПОТЕРЕ денежных средств!
❗ Отправляйте USDT только в сети TRC20! Отправка в другой сети приведёт к безвозвратной потере средств!
❗ Проверяйте реквизиты перед переводом!

После перевода отправьте скриншот в бот!
"""

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== ПРОВЕРКА ПРАВ ====================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_super_admin(user_id):
    return user_id == SUPER_ADMIN_ID

def get_admin_role(user_id):
    if user_id == SUPER_ADMIN_ID:
        return "СУПЕР-АДМИН"
    elif user_id == SUPPORT_ADMIN_ID:
        return "МЕНЕДЖЕР"
    return "ПОЛЬЗОВАТЕЛЬ"

# ==================== КЛАВИАТУРЫ ====================
async def get_gifts_keyboard():
    gifts = await get_all_gifts()
    builder = InlineKeyboardBuilder()
    for gift in gifts:
        builder.button(
            text=f"💎 {gift['name']} | {int(gift['price'])}₽",
            callback_data=f"gift_{gift['id']}"
        )
    builder.adjust(1)
    return builder.as_markup()

async def get_payment_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои реквизиты", callback_data="show_requisites")
    builder.button(text="⬅️ Назад к подаркам", callback_data="back_to_gifts")
    builder.adjust(1)
    return builder.as_markup()

async def get_gift_detail_keyboard(gift_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить", callback_data=f"pay_{gift_id}")
    builder.button(text="⬅️ Назад к подаркам", callback_data="back_to_gifts")
    builder.adjust(2)
    return builder.as_markup()

async def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад к подаркам", callback_data="back_to_gifts")
    builder.adjust(1)
    return builder.as_markup()

async def get_super_admin_keyboard():
    """Полная админ-панель для супер-админа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="📢 Рассылка", callback_data="admin_broadcast")
    builder.button(text="⚙️ Настройки", callback_data="admin_settings")
    builder.button(text="🔧 Помощь", callback_data="admin_help")
    builder.adjust(2)
    return builder.as_markup()

async def get_support_admin_keyboard():
    """Ограниченная панель для менеджера"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="💬 Сообщения", callback_data="admin_messages")
    builder.button(text="📊 Моя статистика", callback_data="admin_support_stats")
    builder.adjust(2)
    return builder.as_markup()

async def get_admin_keyboard(user_id):
    """Выбор клавиатуры в зависимости от роли"""
    if is_super_admin(user_id):
        return await get_super_admin_keyboard()
    else:
        return await get_support_admin_keyboard()

# ==================== ХЕНДЛЕРЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username)
    
    # Если админ — показываем админ-панель
    if is_admin(message.from_user.id):
        role = get_admin_role(message.from_user.id)
        await message.answer(
            f"👋 <b>Привет, {role}!</b>\n\n"
            f"Выбери действие:",
            parse_mode="HTML",
            reply_markup=await get_admin_keyboard(message.from_user.id)
        )
    else:
        await message.answer(
            f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
            f"Выбери подарок ниже 👇\n\n"
            f"💳 Оплата вручную (СБП/карта/крипта)\n"
            f"📱 После оплаты отправь скриншот в бот\n"
            f"⏱️ Вручаю подарки в течение 24 часов",
            parse_mode="HTML",
            reply_markup=await get_gifts_keyboard()
        )

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        f"⚙️ <b>Админ-панель</b>\n\n"
        f"Твоя роль: {get_admin_role(message.from_user.id)}\n"
        f"Выбери действие:",
        parse_mode="HTML",
        reply_markup=await get_admin_keyboard(message.from_user.id)
    )

@dp.callback_query(F.data.startswith("admin_"))
async def admin_panel(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    action = callback.data.split("_")[1]
    
    # === ДОСТУПНО ВСЕМ АДМИНАМ ===
    if action == "orders":
        transactions = await get_all_transactions()
        if not transactions:
            await callback.message.answer("📦 Заказов ещё нет")
            return
        
        recent = transactions[-10:][::-1]
        text = "📦 <b>Последние заказы:</b>\n\n"
        for t in recent:
            text += f"💰 {t['amount']}₽ | {t['gift_name']} | @{t.get('username', 'нет')}\n"
        
        await callback.message.answer(text, parse_mode="HTML")
    
    # === ТОЛЬКО СУПЕР-АДМИН ===
    elif action == "stats":
        if not is_super_admin(callback.from_user.id):
            await callback.answer("❌ Только супер-админ", show_alert=True)
            return
        
        transactions = await get_all_transactions()
        total_income = sum(t['amount'] for t in transactions)
        total_fee = sum(t['fee'] for t in transactions)
        
        # Расчёт распределения прибыли
        lana_share = total_fee * PROFIT_SPLIT['lana']
        admin_share = total_fee * PROFIT_SPLIT['admin']
        dev_share = total_fee * PROFIT_SPLIT['development']
        tax_share = total_fee * PROFIT_SPLIT['tax']
        
        await callback.message.answer(
            f"📊 <b>Полная статистика бота</b>\n\n"
            f"📦 Всего заказов: {len(transactions)}\n"
            f"💵 Общий оборот: {int(total_income)}₽\n"
            f"💰 Комиссия (10%): {int(total_fee)}₽\n\n"
            f"📈 <b>Распределение прибыли:</b>\n"
            f"👤 Лана (47%): {int(lana_share)}₽\n"
            f"👤 Я (28%): {int(admin_share)}₽\n"
            f"🚀 Развитие (19%): {int(dev_share)}₽\n"
            f"📋 Налог (6%): {int(tax_share)}₽\n\n"
            f"✅ Успешных: {len(transactions)}",
            parse_mode="HTML"
        )
    
    elif action == "users":
        if not is_super_admin(callback.from_user.id):
            await callback.answer("❌ Только супер-админ", show_alert=True)
            return
        
        await callback.message.answer(
            f"👥 <b>Пользователи</b>\n\n"
            f"Функция в разработке.\n"
            f"Данные хранятся в базе данных Neon.",
            parse_mode="HTML"
        )
    
    elif action == "broadcast":
        if not is_super_admin(callback.from_user.id):
            await callback.answer("❌ Только супер-админ", show_alert=True)
            return
        
        await callback.message.answer(
            f"📢 <b>Рассылка</b>\n\n"
            f"Отправь сообщение, которое нужно разослать всем пользователям.\n"
            f"Или отмени командой /cancel",
            parse_mode="HTML"
        )
    
    elif action == "settings":
        if not is_super_admin(callback.from_user.id):
            await callback.answer("❌ Только супер-админ", show_alert=True)
            return
        
        await callback.message.answer(
            f"⚙️ <b>Настройки</b>\n\n"
            f"Здесь можно изменить:\n"
            f"• Реквизиты для оплаты\n"
            f"• Комиссию\n"
            f"• Список подарков\n\n"
            f"Изменения вносятся через код на GitHub.",
            parse_mode="HTML"
        )
    
    elif action == "help":
        if not is_super_admin(callback.from_user.id):
            await callback.answer("❌ Только супер-админ", show_alert=True)
            return
        
        await callback.message.answer(
            f"🔧 <b>Помощь супер-админу</b>\n\n"
            f"📊 /stats - Полная статистика\n"
            f"👥 /users - Список пользователей\n"
            f"📦 /orders - Заказы\n"
            f"📢 /broadcast - Рассылка\n"
            f"⚙️ /settings - Настройки\n"
            f"❓ /help - Эта справка",
            parse_mode="HTML"
        )
    
    # === ТОЛЬКО МЕНЕДЖЕР ===
    elif action == "messages":
        if callback.from_user.id == SUPPORT_ADMIN_ID:
            await callback.message.answer(
                f"💬 <b>Сообщения от клиентов</b>\n\n"
                f"Все сообщения пересылаются тебе автоматически.\n"
                f"Проверяй личные сообщения от бота.",
                parse_mode="HTML"
            )
    
    elif action == "support_stats":
        transactions = await get_all_transactions()
        total_income = sum(t['amount'] for t in transactions)
        
        await callback.message.answer(
            f"📊 <b>Твоя статистика (Менеджер)</b>\n\n"
            f"📦 Всего заказов: {len(transactions)}\n"
            f"💵 Общий оборот: {int(total_income)}₽\n"
            f"✅ Обработано: {len(transactions)}",
            parse_mode="HTML"
        )
    
    await callback.answer()

@dp.callback_query(F.data.startswith("gift_"))
async def process_gift_select(callback: types.CallbackQuery):
    gift_id = int(callback.data.split("_")[1])
    gifts = await get_all_gifts()
    gift = next((g for g in gifts if g['id'] == gift_id), None)
    
    if not gift:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return

    await callback.message.answer(
        f"🎁 <b>{gift['name']}</b>\n\n"
        f"💰 <b>Цена:</b> {int(gift['price'])}₽\n"
        f"📝 <b>Описание:</b>\n{gift['description']}\n\n"
        f"Нажми кнопку для оплаты:",
        parse_mode="HTML",
        reply_markup=await get_gift_detail_keyboard(gift_id)
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_gifts")
async def back_to_gifts(callback: types.CallbackQuery):
    if is_admin(callback.from_user.id):
        await callback.message.edit_text(
            f"⚙️ <b>Админ-панель</b>\n\n"
            f"Твоя роль: {get_admin_role(callback.from_user.id)}\n"
            f"Выбери действие:",
            parse_mode="HTML",
            reply_markup=await get_admin_keyboard(callback.from_user.id)
        )
    else:
        await callback.message.edit_text(
            "👋 Выбери подарок ниже 👇",
            reply_markup=await get_gifts_keyboard()
        )
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: types.CallbackQuery):
    gift_id = int(callback.data.split("_")[1])
    gifts = await get_all_gifts()
    gift = next((g for g in gifts if g['id'] == gift_id), None)
    
    if not gift:
        await callback.answer("❌ Подарок не найден", show_alert=True)
        return

    fee = gift['price'] * FEE_PERCENT
    await add_transaction(callback.from_user.id, gift['name'], gift['price'], fee)
    
    # Расчёт распределения
    lana_share = fee * PROFIT_SPLIT['lana']
    admin_share = fee * PROFIT_SPLIT['admin']
    dev_share = fee * PROFIT_SPLIT['development']
    tax_share = fee * PROFIT_SPLIT['tax']
    
    await callback.message.answer(
        f"✅ <b>Инструкция по оплате:</b>\n\n"
        f"🎁 Подарок: {gift['name']}\n"
        f"💰 Сумма: {int(gift['price'])}₽\n\n"
        f"{PAYMENT_DETAILS}\n\n"
        f"⚠️ <b>Порядок действий:</b>\n"
        f"1️⃣ Переведи точную сумму по реквизитам выше\n"
        f"2️⃣ Сделай скриншот успешного перевода\n"
        f"3️⃣ Отправь скриншот в этот чат\n"
        f"4️⃣ Я проверю и вручу подарок в течение 24 часов\n\n"
        f"📞 <b>Есть вопросы?</b> Пиши админу!",
        parse_mode="HTML",
        reply_markup=await get_payment_keyboard()
    )
    
    # Уведомляем ОБАИХ админов
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"💰 <b>Новый заказ!</b>\n\n"
            f"👤 Юзер: @{callback.from_user.username or 'без username'}\n"
            f"🆔 ID: {callback.from_user.id}\n"
            f"💵 Сумма: {int(gift['price'])}₽\n"
            f"💰 Комиссия: {int(fee)}₽\n\n"
            f"📈 <b>Распределение:</b>\n"
            f"👤 Лана (47%): {int(lana_share)}₽\n"
            f"👤 Я (28%): {int(admin_share)}₽\n"
            f"🚀 Развитие (19%): {int(dev_share)}₽\n"
            f"📋 Налог (6%): {int(tax_share)}₽\n\n"
            f"📱 Ждём скриншот оплаты",
            parse_mode="HTML"
        )
    
    await callback.answer()

@dp.callback_query(F.data == "show_requisites")
async def show_requisites(callback: types.CallbackQuery):
    await callback.message.answer(
        f"📋 <b>Реквизиты для оплаты:</b>\n\n"
        f"{PAYMENT_DETAILS}",
        parse_mode="HTML"
    )
    await callback.answer()

# ==================== ОБРАБОТКА СКРИНШОТОВ ====================
@dp.message(F.photo)
async def handle_screenshot(message: types.Message):
    await message.forward(SUPPORT_ADMIN_ID)
    
    await message.answer(
        f"✅ <b>Скриншот получен!</b>\n\n"
        f"🕒 Я проверю оплату и вручу подарок в течение 24 часов.\n"
        f"📞 Если возникнут вопросы — я свяжусь с тобой.\n\n"
        f"Спасибо за терпение! 🙏",
        parse_mode="HTML"
    )
    
    # Пересылаем обоим админам
    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"📸 <b>Новый скриншот оплаты!</b>\n\n"
            f"👤 От: @{message.from_user.username or 'без username'}\n"
            f"🆔 ID: {message.from_user.id}\n"
            f"💳 Проверь поступление средств и вручи подарок!",
            parse_mode="HTML"
        )

# ==================== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ====================
@dp.message()
async def handle_text(message: types.Message):
    # Игнорируем команды
    if message.text.startswith('/'):
        return
    
    # Пересылаем менеджеру (7076299389)
    await message.forward(SUPPORT_ADMIN_ID)
    
    await message.answer(
        f"✅ <b>Сообщение отправлено менеджеру!</b>\n\n"
        f"Я отвечу тебе в ближайшее время.",
        parse_mode="HTML"
    )
    
    # Уведомляем супер-админа
    await bot.send_message(
        SUPER_ADMIN_ID,
        f"💬 <b>Новое сообщение от пользователя!</b>\n\n"
        f"👤 От: @{message.from_user.username or 'без username'}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"📝 Текст: {message.text}",
        parse_mode="HTML"
    )

# ==================== АДМИН-КОМАНДЫ ====================
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    if not is_super_admin(message.from_user.id):
        await message.answer("❌ Только супер-админ")
        return
    
    transactions = await get_all_transactions()
    total_income = sum(t['amount'] for t in transactions)
    total_fee = sum(t['fee'] for t in transactions)
    
    # Расчёт распределения прибыли
    lana_share = total_fee * PROFIT_SPLIT['lana']
    admin_share = total_fee * PROFIT_SPLIT['admin']
    dev_share = total_fee * PROFIT_SPLIT['development']
    tax_share = total_fee * PROFIT_SPLIT['tax']
    
    await message.answer(
        f"📊 <b>Полная статистика бота</b>\n\n"
        f"📦 Всего заказов: {len(transactions)}\n"
        f"💵 Общий оборот: {int(total_income)}₽\n"
        f"💰 Комиссия (10%): {int(total_fee)}₽\n\n"
        f"📈 <b>Распределение прибыли:</b>\n"
        f"👤 Лана (47%): {int(lana_share)}₽\n"
        f"👤 Я (28%): {int(admin_share)}₽\n"
        f"🚀 Развитие (19%): {int(dev_share)}₽\n"
        f"📋 Налог (6%): {int(tax_share)}₽\n\n"
        f"✅ Успешных: {len(transactions)}",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    if is_super_admin(message.from_user.id):
        await message.answer(
            f"📚 <b>Помощь (Супер-админ)</b>\n\n"
            f"🎁 <b>/start</b> - Админ-панель\n"
            f"⚙️ <b>/admin</b> - Админ-панель\n"
            f"📊 <b>/stats</b> - Полная статистика\n"
            f"🗑️ <b>/reset_stats</b> - Сброс статистики\n"
            f"👥 <b>/users</b> - Список пользователей\n"
            f"📦 <b>/orders</b> - Список заказов\n"
            f"📢 <b>/broadcast</b> - Рассылка всем\n"
            f"⚙️ <b>/settings</b> - Настройки\n"
            f"❓ <b>/help</b> - Эта справка",
            parse_mode="HTML"
        )
    elif is_admin(message.from_user.id):
        await message.answer(
            f"📚 <b>Помощь (Менеджер)</b>\n\n"
            f"🎁 <b>/start</b> - Админ-панель\n"
            f"⚙️ <b>/admin</b> - Админ-панель\n"
            f"📦 <b>/orders</b> - Список заказов\n"
            f"💬 <b>/messages</b> - Сообщения клиентов\n"
            f"❓ <b>/help</b> - Эта справка",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"📚 <b>Помощь</b>\n\n"
            f"🎁 <b>/start</b> - Главное меню с подарками\n"
            f"❓ <b>/help</b> - Эта справка\n\n"
            f"💡 Если возникли вопросы — пиши админу!",
            parse_mode="HTML"
        )

@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    if not is_super_admin(message.from_user.id):
        await message.answer("❌ Только супер-админ")
        return
    
    await message.answer(
        f"👥 <b>Пользователи</b>\n\n"
        f"Функция в разработке.\n"
        f"Данные хранятся в базе данных Neon.",
        parse_mode="HTML"
    )

@dp.message(Command("orders"))
async def cmd_orders(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    transactions = await get_all_transactions()
    if not transactions:
        await message.answer("📦 Заказов ещё нет")
        return
    
    recent = transactions[-10:][::-1]
    text = "📦 <b>Последние 10 заказов:</b>\n\n"
    for t in recent:
        text += f"💰 {t['amount']}₽ | {t['gift_name']} | @{t.get('username', 'нет')}\n"
    
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: types.Message):
    if not is_super_admin(message.from_user.id):
        await message.answer("❌ Только супер-админ")
        return
    
    await message.answer(
        f"📢 <b>Рассылка</b>\n\n"
        f"Отправь сообщение, которое нужно разослать всем пользователям.\n"
        f"Или отмени командой /cancel",
        parse_mode="HTML"
    )

@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    if not is_super_admin(message.from_user.id):
        await message.answer("❌ Только супер-админ")
        return
    
    await message.answer(
        f"⚙️ <b>Настройки</b>\n\n"
        f"Изменения вносятся через код на GitHub:\n"
        f"• Реквизиты для оплаты\n"
        f"• Комиссия\n"
        f"• Список подарков\n"
        f"• Распределение прибыли",
        parse_mode="HTML"
    )

@dp.message(Command("messages"))
async def cmd_messages(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        f"💬 <b>Сообщения от клиентов</b>\n\n"
        f"Все сообщения пересылаются автоматически.\n"
        f"Проверяй личные сообщения от бота.",
        parse_mode="HTML"
    )

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    await message.answer("❌ Отменено")

# ==================== СБРОС СТАТИСТИКИ ====================
@dp.message(Command("reset_stats"))
async def cmd_reset_stats(message: types.Message):
    if not is_super_admin(message.from_user.id):
        await message.answer("❌ Только супер-админ!")
        return
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, сбросить", callback_data="confirm_reset_stats")
    builder.button(text="❌ Отмена", callback_data="cancel_reset_stats")
    builder.adjust(2)
    
    await message.answer(
        f"⚠️ <b>Сброс статистики</b>\n\n"
        f"Вы уверены, что хотите удалить ВСЕ транзакции?\n"
        f"Это действие нельзя отменить!",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "confirm_reset_stats")
async def confirm_reset_stats(callback: types.CallbackQuery):
    if not is_super_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    try:
        await clear_transactions()
        
        await callback.message.answer(
            f"✅ <b>Статистика сброшена!</b>\n\n"
            f"Все транзакции удалены.\n"
            f"Бот готов к новой работе! 🚀",
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    
    await callback.answer()

@dp.callback_query(F.data == "cancel_reset_stats")
async def cancel_reset_stats(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("❌ Отменено")

# ==================== ЗАПУСК ====================
async def main():
    print("🔄 Инициализация базы данных...")
    await init_db()
    
    print("🔔 Запуск веб-сервера для UptimeRobot...")
    keep_alive()
    
    print("🚀 Бот запущен! Работаю 24/7!")
    print(f"👑 Супер-админ: {SUPER_ADMIN_ID}")
    print(f"👤 Менеджер: {SUPPORT_ADMIN_ID}")
    print(f"💰 Распределение прибыли:")
    print(f"   👤 Лана: {PROFIT_SPLIT['lana']*100:.0f}%")
    print(f"   👤 Я: {PROFIT_SPLIT['admin']*100:.0f}%")
    print(f"   🚀 Развитие: {PROFIT_SPLIT['development']*100:.0f}%")
    print(f"   📋 Налог: {PROFIT_SPLIT['tax']*100:.0f}%")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


