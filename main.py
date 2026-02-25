import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import init_db, get_user, add_user, get_all_gifts, add_transaction, get_all_transactions
from keep_alive import keep_alive

# ==================== КОНФИГ ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = 7076299389  # Твой ID админа
FEE_PERCENT = 0.10

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

# ==================== ХЕНДЛЕРЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username)
    
    await message.answer(
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"Выбери подарок ниже 👇\n\n"
        f"💳 Оплата вручную (СБП/карта/крипта)\n"
        f"📱 После оплаты отправь скриншот в бот\n"
        f"⏱️ Вручаю подарки в течение 24 часов",
        parse_mode="HTML",
        reply_markup=await get_gifts_keyboard()
    )

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

    # Записываем транзакцию в БД
    fee = gift['price'] * FEE_PERCENT
    await add_transaction(callback.from_user.id, gift['name'], gift['price'], fee)
    
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
        f"📞 <b>Есть вопросы?</b> Пиши админу: @{(await bot.get_me()).username}",
        parse_mode="HTML",
        reply_markup=await get_payment_keyboard()
    )
    
    # Уведомляем админа
    await bot.send_message(
        ADMIN_ID,
        f"💰 <b>Новый заказ!</b>\n\n"
        f"👤 Юзер: @{callback.from_user.username or 'без username'}\n"
        f"🆔 ID: {callback.from_user.id}\n"
        f"💵 Сумма: {int(gift['price'])}₽\n"
        f"🎁 Подарок: {gift['name']}\n"
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
    # Пересылаем скриншот админу
    await message.forward(ADMIN_ID)
    
    await message.answer(
        f"✅ <b>Скриншот получен!</b>\n\n"
        f"🕒 Я проверю оплату и вручу подарок в течение 24 часов.\n"
        f"📞 Если возникнут вопросы — я свяжусь с тобой.\n\n"
        f"Спасибо за терпение! 🙏",
        parse_mode="HTML"
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"📸 <b>Новый скриншот оплаты!</b>\n\n"
        f"👤 От: @{message.from_user.username or 'без username'}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"💳 Проверь поступление средств и вручи подарок!",
        parse_mode="HTML"
    )

# ==================== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ====================
@dp.message()
async def handle_text(message: types.Message):
    # Пересылаем все текстовые сообщения админу (для связи)
    if message.text:
        await message.forward(ADMIN_ID)
        
        await message.answer(
            f"✅ <b>Сообщение отправлено админу!</b>\n\n"
            f"Я отвечу тебе в ближайшее время.",
            parse_mode="HTML"
        )
        
        await bot.send_message(
            ADMIN_ID,
            f"💬 <b>Новое сообщение от пользователя!</b>\n\n"
            f"👤 От: @{message.from_user.username or 'без username'}\n"
            f"🆔 ID: {message.from_user.id}\n"
            f"📝 Текст: {message.text}",
            parse_mode="HTML"
        )

# ==================== АДМИН-КОМАНДЫ ====================
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещён")
        return
    
    transactions = await get_all_transactions()
    total_income = sum(t['amount'] for t in transactions)
    total_fee = sum(t['fee'] for t in transactions)
    
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"📦 Всего заказов: {len(transactions)}\n"
        f"💵 Общий оборот: {int(total_income)}₽\n"
        f"💰 Твоя прибыль (10%): {int(total_fee)}₽",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        f"📚 <b>Помощь</b>\n\n"
        f"🎁 <b>/start</b> - Главное меню с подарками\n"
        f"📊 <b>/stats</b> - Статистика (только админ)\n"
        f"❓ <b>/help</b> - Эта справка\n\n"
        f"💡 Если возникли вопросы — пиши админу!",
        parse_mode="HTML"
    )

# ==================== ЗАПУСК ====================
async def main():
    print("🔄 Инициализация базы данных...")
    await init_db()
    
    print("🔔 Запуск веб-сервера для UptimeRobot...")
    keep_alive()
    
    print("🚀 Бот запущен! Работаю 24/7!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



