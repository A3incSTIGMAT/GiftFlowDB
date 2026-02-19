import os
import asyncio
import hashlib
import hmac
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import ClientSession, web
from database import init_db, get_user, add_user, get_all_gifts, add_transaction, get_all_transactions
from keep_alive import keep_alive

# ==================== КОНФИГ ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')
LAVA_SHOP_ID = os.getenv('LAVA_SHOP_ID')
LAVA_API_KEY = os.getenv('LAVA_API_KEY')
LAVA_SECRET_KEY = os.getenv('LAVA_SECRET_KEY')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
FEE_PERCENT = 0.10  # Твоя комиссия 10%

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== LAVA ФУНКЦИИ ====================
async def create_lava_invoice(amount, order_id, description):
    """Создаёт счёт в Lava.top"""
    url = "https://api.lava.top/payment/create"
    headers = {
        "Authorization": f"Bearer {LAVA_API_KEY}",
        "Content-Type": "application/json",
        "Shop-Id": LAVA_SHOP_ID
    }
    data = {
        "amount": str(amount),
        "currency": "RUB",
        "orderId": order_id,
        "description": description,
        "successUrl": f"https://t.me/{(await bot.get_me()).username}",
        "failUrl": f"https://t.me/{(await bot.get_me()).username}",
        "webhookUrl": "https://giftflowdb.onrender.com/webhook"
    }
    
    async with ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            return await response.json()

def verify_lava_signature(data, signature):
    """Проверяет подпись от Lava"""
    sign_string = f"{data.get('orderId', '')}{data.get('amount', '')}{LAVA_SECRET_KEY}"
    hash = hashlib.sha256(sign_string.encode()).hexdigest()
    return hash == signature

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
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Оплатить счет", url=invoice_url)
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
        f"💳 Оплата через Lava (СБП/карты/крипта)\n"
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

    order_id = f"{callback.from_user.id}_{gift['id']}_{int(gift['price'])}"
    
    result = await create_lava_invoice(
        amount=gift['price'],
        order_id=order_id,
        description=f"Подарок: {gift['name']}"
    )
    
    print(f"Lava API Response: {result}")
    
    if result.get('success') or result.get('url') or result.get('paymentUrl'):
        invoice_url = result.get('url', result.get('paymentUrl', result.get('data', {}).get('url', '')))
        
        if invoice_url:
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
            
            await bot.send_message(
                ADMIN_ID,
                f"💰 <b>Новый счет Lava!</b>\n\n"
                f"👤 Юзер: @{callback.from_user.username or 'без username'}\n"
                f"💵 Сумма: {int(gift['price'])}₽\n"
                f"🎁 Подарок: {gift['name']}\n"
                f"🔗 <a href='{invoice_url}'>Ссылка на оплату</a>",
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                "❌ Ошибка: не удалось получить ссылку на оплату.\nПопробуй позже или напиши админу.",
                reply_markup=await get_back_keyboard()
            )
    else:
        error_msg = result.get('message', result.get('error', 'Неизвестная ошибка'))
        await callback.message.answer(
            f"❌ Ошибка создания счета: {error_msg}\nПопробуй позже или напиши админу.",
            reply_markup=await get_back_keyboard()
        )
    
    await callback.answer()

# ==================== WEBHOOK ДЛЯ LAVA ====================
async def lava_webhook_handler(request):
    """Обработчик уведомлений от Lava"""
    try:
        data = await request.json()
        signature = request.headers.get('X-Signature', '')
        
        print(f"Lava Webhook: {data}")
        
        if not verify_lava_signature(data, signature):
            print("Invalid signature")
            return web.json_response({'status': 'error'}, status=400)
        
        if data.get('status') == 'paid' or data.get('success') == True:
            order_id = data.get('orderId', data.get('order_id', ''))
            amount = float(data.get('amount', 0))
            user_id = int(order_id.split('_')[0]) if '_' in order_id else 0
            
            await bot.send_message(
                ADMIN_ID,
                f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
                f"👤 User ID: {user_id}\n"
                f"💵 Сумма: {int(amount)}₽\n"
                f"🎉 Пора вручать подарок!",
                parse_mode="HTML"
            )
        
        return web.json_response({'status': 'success'})
    except Exception as e:
        print(f"Webhook error: {e}")
        return web.json_response({'status': 'error'}, status=500)

# ==================== АДМИН-КОМАНДЫ ====================
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
    
    print("🔔 Запуск веб-сервера для Lava Webhook + UptimeRobot...")
    keep_alive()
    
    print("🚀 Бот запущен! Работаю 24/7!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())



