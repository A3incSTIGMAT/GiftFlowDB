import os
import asyncio
import hashlib
import urllib.parse
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import ClientSession, web
from database import init_db, get_user, add_user, get_all_gifts, add_transaction, get_all_transactions
from keep_alive import keep_alive

# ==================== КОНФИГ ====================
BOT_TOKEN = os.getenv('BOT_TOKEN')
ROBOKASSA_LOGIN = os.getenv('ROBOKASSA_LOGIN')
ROBOKASSA_PASSWORD_1 = os.getenv('ROBOKASSA_PASSWORD_1')
ROBOKASSA_PASSWORD_2 = os.getenv('ROBOKASSA_PASSWORD_2')
OFFER_URL = os.getenv('OFFER_URL')  # Ссылка на оферту
ADMIN_ID = int(os.getenv('ADMIN_ID'))
FEE_PERCENT = 0.10

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== ROBOKASSA ФУНКЦИИ ====================
def create_robokassa_payment_url(order_id, amount, description):
    """Создаёт ссылку на оплату Robokassa"""
    base_url = "https://auth.robokassa.ru/Merchant/Index.aspx"
    
    params = {
        'MrchLogin': ROBOKASSA_LOGIN,
        'OutSum': str(amount),
        'InvId': str(order_id),
        'Desc': description,
        'SignatureValue': generate_signature(amount, order_id)
    }
    
    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"

def generate_signature(amount, order_id):
    """Генерирует подпись для Robokassa"""
    signature_string = f"{ROBOKASSA_LOGIN}:{amount}:{order_id}:{ROBOKASSA_PASSWORD_1}"
    return hashlib.md5(signature_string.encode('utf-8')).hexdigest()

def verify_robokassa_signature(amount, order_id, signature):
    """Проверяет подпись от Robokassa"""
    signature_string = f"{amount}:{order_id}:{ROBOKASSA_PASSWORD_2}"
    expected_signature = hashlib.md5(signature_string.encode('utf-8')).hexdigest()
    return signature_string.upper() == signature.upper()

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
        f"💳 Оплата через Robokassa (СБП/карты)\n"
        f"🔒 Безопасно и официально\n\n"
        f"📄 <a href='{OFFER_URL}'>Публичная оферта</a>",
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
        f"📄 <a href='{OFFER_URL}'>Оферта</a>\n\n"
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
    
    # Создаём ссылку на оплату Robokassa
    invoice_url = create_robokassa_payment_url(
        order_id=order_id,
        amount=gift['price'],
        description=f"Подарок: {gift['name']}"
    )
    
    print(f"Robokassa URL: {invoice_url}")
    
    if invoice_url:
        fee = gift['price'] * FEE_PERCENT
        await add_transaction(callback.from_user.id, gift['name'], gift['price'], fee)
        
        await callback.message.answer(
            f"✅ <b>Счет создан!</b>\n\n"
            f"💰 Сумма: {int(gift['price'])}₽\n"
            f"🎁 Подарок: {gift['name']}\n\n"
            f"📄 <a href='{OFFER_URL}'>Оферта</a>\n\n"
            f"Оплати по кнопке ниже:",
            parse_mode="HTML",
            reply_markup=await get_payment_keyboard(invoice_url)
        )
        
        await bot.send_message(
            ADMIN_ID,
            f"💰 <b>Новый счет Robokassa!</b>\n\n"
            f"👤 Юзер: @{callback.from_user.username or 'без username'}\n"
            f"💵 Сумма: {int(gift['price'])}₽\n"
            f"🎁 Подарок: {gift['name']}\n"
            f"🔗 <a href='{invoice_url}'>Ссылка на оплату</a>",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer(
            "❌ Ошибка создания счета.\nПопробуй позже или напиши админу.",
            reply_markup=await get_back_keyboard()
        )
    
    await callback.answer()

# ==================== WEBHOOK ДЛЯ ROBOKASSA ====================
async def robokassa_webhook_handler(request):
    """Обработчик уведомлений от Robokassa"""
    try:
        data = await request.post()
        
        amount = data.get('OutSum')
        order_id = data.get('InvId')
        signature = data.get('SignatureValue')
        
        print(f"Robokassa Webhook: amount={amount}, order_id={order_id}")
        
        # Проверяем подпись
        if verify_robokassa_signature(amount, order_id, signature):
            # Уведомляем админа об успешной оплате
            user_id = int(order_id.split('_')[0]) if '_' in order_id else 0
            
            await bot.send_message(
                ADMIN_ID,
                f"✅ <b>ОПЛАТА ПОДТВЕРЖДЕНА!</b>\n\n"
                f"👤 User ID: {user_id}\n"
                f"💵 Сумма: {int(float(amount))}₽\n"
                f"🎉 Пора вручать подарок!",
                parse_mode="HTML"
            )
            
            return web.Response(text=f"OK{order_id}")
        else:
            print("Invalid signature")
            return web.Response(text="Bad Signature", status=400)
            
    except Exception as e:
        print(f"Webhook error: {e}")
        return web.Response(text="Error", status=500)

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
        f"📚 <b>Помощь</b>\n\n"
        f"🎁 <b>/start</b> - Главное меню с подарками\n"
        f"📊 <b>/stats</b> - Статистика (только админ)\n"
        f"📄 <b>/offer</b> - Публичная оферта\n"
        f"❓ <b>/help</b> - Эта справка\n\n"
        f"💡 Если возникли вопросы — пиши админу!",
        parse_mode="HTML"
    )

@dp.message(Command("offer"))
async def cmd_offer(message: types.Message):
    await message.answer(
        f"📄 <b>Публичная оферта</b>\n\n"
        f"Ознакомьтесь с условиями:\n"
        f"🔗 {OFFER_URL}",
        parse_mode="HTML"
    )

# ==================== ЗАПУСК ====================
async def main():
    print("🔄 Инициализация базы данных...")
    await init_db()
    
    print("🔔 Запуск веб-сервера для Robokassa Webhook + UptimeRobot...")
    keep_alive()
    
    print("🚀 Бот запущен! Работаю 24/7!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

