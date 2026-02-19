import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import ClientSession
from database import init_db, get_user, add_user, get_all_gifts, add_transaction, get_all_transactions
from keep_alive import keep_alive

# ==================== КОНФИГ ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')
CRYPTO_TOKEN = os.getenv('CRYPTO_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
FEE_PERCENT = 0.10  # Твоя комиссия 10%

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

async def get_payment_keyboard(invoice_url):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить счет", url=invoice_url)]
    ])

async def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к подаркам", callback_data="back_to_gifts")]
    ])

# ==================== ХЕНДЛЕРЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(message.from_user.id, message.from_user.username)
    
    await message.answer(
        f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
        f"Выбери подарок ниже 👇\n\n"
        f"💳 Оплата через Crypto Bot (карты/крипта)\n"
        f"🔒 Безопасно и анонимно",
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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{gift_id}")]
        ]) + await get_back_keyboard()
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

    # Создаем счет в Crypto Bot
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"X-Crypto-Api-Key": CRYPTO_TOKEN}
    data = {
        "amount": str(int(gift['price'])),
        "asset": "RUB",
        "description": f"Подарок: {gift['name']}",
        "paid_btn_name": "Вернуться в бота",
        "paid_btn_url": f"https://t.me/{(await bot.get_me()).username}",
        "payload": str(callback.from_user.id)
    }
    
    try:
        async with ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                result = await response.json()
                
                if result.get('ok'):
                    invoice_url = result['result']['invoice_url']
                    invoice_id = result['result']['invoice_id']
                    
                    # Записываем транзакцию в БД
                    fee = gift['price'] * FEE_PERCENT
                    await add_transaction(callback.from_user.id, gift['name'], gift['price'], fee)
                    
                    await callback.message.answer(
                        f"✅ <b>Счет создан!</b>\n\n"
                        f"💰 Сумма: {int(gift['price'])}₽\n"
                        f"🎁 Подарок: {gift['name']}\n\n"
                        f"Оплати по кнопке ниже:",
                        parse_mode="HTML",
                        reply_markup=await get_payment_keyboard(invoice_url)
                    )
                    
                    # Уведомляем админа
                    await bot.send_message(
                        ADMIN_ID,
                        f"💰 <b>Новый счет!</b>\n\n"
                        f"👤 Юзер: @{callback.from_user.username or 'без username'}\n"
                        f"💵 Сумма: {int(gift['price'])}₽\n"
                        f"🎁 Подарок: {gift['name']}\n"
                        f"📋 ID инвойса: <code>{invoice_id}</code>\n\n"
                        f"🔗 <a href='{invoice_url}'>Ссылка на оплату</a>",
                        parse_mode="HTML"
                    )
                else:
                    await callback.message.answer(
                        "❌ Ошибка создания счета.\nПопробуй позже или напиши админу.",
                        reply_markup=await get_back_keyboard()
                    )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {str(e)}")
    
    await callback.answer()

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещён")
        return
    
    transactions = await get_all_transactions()
    total_income = sum(t['amount'] for t in transactions)
    total_fee = sum(t['fee'] for t in transactions)
    pending = sum(1 for t in transactions if t['status'] == 'pending')
    
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"📦 Всего транзакций: {len(transactions)}\n"
        f"⏳ Ожидают подтверждения: {pending}\n"
        f"💵 Общий оборот: {int(total_income)}₽\n"
        f"💰 Твоя прибыль (10%): {int(total_fee)}₽\n\n"
        f"📈 Успешных: {len(transactions) - pending}",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📚 <b>Помощь</b>\n\n"
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


