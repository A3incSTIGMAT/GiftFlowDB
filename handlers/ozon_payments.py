"""
Оплата подарков через Озон Банк (СБП/QR-код)
"""

import secrets
import time
import asyncio
import logging
from typing import Dict
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS, CHANNEL_ID, TWITCH_URL, INSTAGRAM_URL
from database import add_transaction, get_gift_by_id, update_top_hero, get_top_heroes

logger = logging.getLogger(__name__)
router = Router()
bot: Bot = None


def set_bot(bot_instance: Bot):
    global bot
    bot = bot_instance


# ========== КОНФИГУРАЦИЯ ==========
OZON_CARD_LAST4 = "4436"
OZON_CARD_FULL = "2204 3210 4743 4436"
OZON_BANK_NAME = "Озон Банк"
OZON_RECEIVER = "Александр Б."
OZON_PHONE = "+7 995 253-89-15"
OZON_SBP_QR_URL = "https://finance.ozon.ru/apps/sbp/ozonbankpay/019d2edd-64d5-7781-87ea-fea6bf40d6cf"

AUTO_DELETE_TIME = 300

pending_payments: Dict[str, dict] = {}


async def delete_message_after_delay(message: Message, delay: int = AUTO_DELETE_TIME):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


async def delete_messages(messages: list):
    for msg in messages:
        try:
            await msg.delete()
        except Exception:
            pass


async def notify_top_entry(user_id: int, username: str, amount: int):
    """Уведомление при входе в топ-3"""
    try:
        heroes = await get_top_heroes(limit=3)
        for i, hero in enumerate(heroes):
            if hero['user_id'] == user_id and i < 3:
                medals = ["🥇", "🥈", "🥉"]
                await bot.send_message(
                    CHANNEL_ID,
                    f"🎉 <b>Поздравляем!</b> {medals[i]} @{username or 'Аноним'} вошёл в топ-3 героев канала!\n\n"
                    f"🔥 Текущий вклад: {hero['total_amount']}₽\n"
                    f"💪 Стань первым — дари подарки через бота!",
                    parse_mode="HTML"
                )
                logger.info(f"Уведомление о топ-3 отправлено для {user_id}")
                break
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о топе: {e}")


def get_payment_menu(order_id: str, amount: int, gift_name: str) -> InlineKeyboardMarkup:
    buttons = []
    
    if OZON_SBP_QR_URL:
        buttons.append([InlineKeyboardButton(
            text="📱 Оплатить по QR-коду (СБП)",
            url=OZON_SBP_QR_URL
        )])
    
    buttons.append([InlineKeyboardButton(
        text="💳 Реквизиты для перевода",
        callback_data=f"ozon_requisites_{order_id}"
    )])
    
    buttons.append([InlineKeyboardButton(
        text="✅ Я оплатил(а)",
        callback_data=f"ozon_confirm_{order_id}"
    )])
    
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="ozon_cancel"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_requisites_text(order_id: str, amount: int, gift_name: str) -> str:
    return f"""
💳 <b>Реквизиты для перевода</b>

📱 <b>СБП (по номеру телефона):</b>
   <code>{OZON_PHONE}</code>

💳 <b>По номеру карты:</b>
   <code>{OZON_CARD_FULL}</code>

🏦 <b>Банк:</b> {OZON_BANK_NAME}
👤 <b>Получатель:</b> {OZON_RECEIVER}
💰 <b>Сумма:</b> <code>{amount} ₽</code>

🎁 <b>Подарок:</b> {gift_name}
📝 <b>Номер заказа:</b> <code>{order_id}</code>

💡 <b>Как оплатить:</b>
<b>СПОСОБ 1 — СБП по номеру телефона:</b>
1️⃣ В приложении банка выберите «Перевод по номеру телефона»
2️⃣ Введите номер <code>{OZON_PHONE}</code>
3️⃣ Укажите сумму <code>{amount} ₽</code>
4️⃣ В назначении платежа укажите <code>{order_id}</code>

<b>СПОСОБ 2 — Перевод по номеру карты:</b>
1️⃣ В приложении банка выберите «Перевод по номеру карты»
2️⃣ Введите номер <code>{OZON_CARD_FULL}</code>
3️⃣ Укажите сумму <code>{amount} ₽</code>
4️⃣ В назначении платежа укажите <code>{order_id}</code>

<b>СПОСОБ 3 — QR-код (СБП):</b>
Нажмите кнопку «Оплатить по QR-коду» выше

⚠️ После оплаты обязательно нажмите кнопку <b>"✅ Я оплатил(а)"</b>
"""


def get_requisites_only() -> str:
    return f"""
💳 <b>Реквизиты для перевода</b>

📱 <b>СБП (по номеру телефона):</b>
   <code>{OZON_PHONE}</code>

💳 <b>По номеру карты:</b>
   <code>{OZON_CARD_FULL}</code>

🏦 <b>Банк:</b> {OZON_BANK_NAME}
👤 <b>Получатель:</b> {OZON_RECEIVER}

📝 <b>Назначение платежа:</b> <code>Ваш_Telegram_ID_или_ник</code>
"""


async def create_gift_payment(user_id: int, username: str, gift_id: int, gift_name: str, amount: int) -> str:
    order_id = f"GIFT_{user_id}_{int(time.time())}_{secrets.token_hex(4)}"
    
    pending_payments[order_id] = {
        "user_id": user_id,
        "username": username,
        "gift_id": gift_id,
        "gift_name": gift_name,
        "amount": amount,
        "status": "pending",
        "created_at": time.time()
    }
    
    return order_id


async def send_payment_message(message: Message, gift_id: int, gift_name: str, amount: int):
    order_id = await create_gift_payment(
        message.from_user.id,
        message.from_user.username,
        gift_id,
        gift_name,
        amount
    )
    
    await message.answer(
        f"🎁 <b>Оплата подарка: {gift_name}</b>\n\n"
        f"💰 Сумма: {amount} ₽\n"
        f"📝 Номер заказа: <code>{order_id}</code>\n\n"
        f"⏳ У вас есть {AUTO_DELETE_TIME // 60} минут на оплату.\n\n"
        f"Выберите способ оплаты:",
        parse_mode="HTML",
        reply_markup=get_payment_menu(order_id, amount, gift_name)
    )


@router.message(Command("requisites"))
async def cmd_requisites(message: Message):
    msg = await message.answer(get_requisites_only(), parse_mode="HTML")
    asyncio.create_task(delete_message_after_delay(msg, 60))


@router.message(Command("qr"))
async def cmd_qr(message: Message):
    if OZON_SBP_QR_URL:
        msg = await message.answer(
            f"📱 <b>Оплата по QR-коду</b>\n\n"
            f"Отсканируйте QR-код в приложении любого банка:\n\n"
            f"🔗 <a href='{OZON_SBP_QR_URL}'>Ссылка на QR-код</a>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_message_after_delay(msg, 60))
    else:
        msg = await message.answer("❌ QR-код не настроен")
        asyncio.create_task(delete_message_after_delay(msg, 30))


@router.callback_query(lambda c: c.data and c.data.startswith("ozon_requisites_"))
async def show_requisites(callback: CallbackQuery):
    order_id = callback.data.replace("ozon_requisites_", "")
    
    if order_id not in pending_payments:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    payment = pending_payments[order_id]
    
    msg = await callback.message.answer(
        get_requisites_text(order_id, payment["amount"], payment["gift_name"]),
        parse_mode="HTML"
    )
    asyncio.create_task(delete_message_after_delay(msg, 120))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("ozon_confirm_"))
async def payment_confirmed(callback: CallbackQuery):
    order_id = callback.data.replace("ozon_confirm_", "")
    
    if order_id not in pending_payments:
        await callback.message.edit_text(
            "❌ Заказ не найден. Попробуйте выбрать подарок заново.",
            reply_markup=None
        )
        await callback.answer()
        return
    
    payment = pending_payments[order_id]
    
    await add_transaction(
        payment["user_id"],
        payment["username"],
        payment["gift_id"],
        payment["gift_name"],
        payment["amount"],
        order_id
    )
    
    # Обновляем топ героев
    await update_top_hero(payment["user_id"], payment["username"], payment["amount"])
    
    # Проверяем вход в топ-3
    await notify_top_entry(payment["user_id"], payment["username"], payment["amount"])
    
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    confirm_msg = await callback.message.answer(
        f"✅ <b>Заявка на оплату принята!</b>\n\n"
        f"🎁 Подарок: {payment['gift_name']}\n"
        f"💰 Сумма: {payment['amount']} ₽\n"
        f"📝 Заказ: <code>{order_id}</code>\n\n"
        f"⏳ Администратор проверит оплату в ближайшее время.\n"
        f"После подтверждения подарок будет вручён.",
        parse_mode="HTML"
    )
    
    asyncio.create_task(delete_message_after_delay(confirm_msg, 60))
    
    from config import PROFIT_SPLIT
    
    amount = payment["amount"]
    lana_share = amount * PROFIT_SPLIT['lana']
    admin_share = amount * PROFIT_SPLIT['admin']
    dev_share = amount * PROFIT_SPLIT['development']
    tax_share = amount * PROFIT_SPLIT['tax']
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔔 <b>НОВОЕ ПОДТВЕРЖДЕНИЕ ОПЛАТЫ!</b>\n\n"
                f"👤 Пользователь: {payment['username'] or payment['user_id']}\n"
                f"🆔 ID: {payment['user_id']}\n"
                f"🎁 Подарок: {payment['gift_name']}\n"
                f"💰 Сумма: {amount} ₽\n"
                f"📝 Заказ: <code>{order_id}</code>\n\n"
                f"📈 <b>Распределение:</b>\n"
                f"👤 Лана (47%): {int(lana_share)}₽\n"
                f"👤 Админ (28%): {int(admin_share)}₽\n"
                f"🚀 Развитие (19%): {int(dev_share)}₽\n"
                f"📋 Налог (6%): {int(tax_share)}₽\n\n"
                f"✅ /approve_{order_id} — подтвердить и вручить подарок\n"
                f"❌ /decline_{order_id} — отклонить",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления админа: {e}")
    
    del pending_payments[order_id]
    
    await callback.answer(
        "✅ Заявка отправлена администратору!",
        show_alert=True
    )


@router.callback_query(lambda c: c.data == "ozon_cancel")
async def payment_cancel(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    cancel_msg = await callback.message.answer(
        "❌ Платёж отменён.\n\n"
        "Выберите другой подарок в каталоге: /start",
        parse_mode="HTML"
    )
    asyncio.create_task(delete_message_after_delay(cancel_msg, 10))
    await callback.answer()


@router.message(Command("approve"))
async def approve_payment(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только администраторы могут использовать эту команду.")
        return
    
    text = message.text
    if " " in text:
        order_id = text.split()[1]
    else:
        order_id = text.replace("/approve_", "")
    
    if order_id not in pending_payments:
        await message.answer("❌ Заказ не найден или уже обработан")
        return
    
    payment = pending_payments[order_id]
    user_id = payment["user_id"]
    gift_name = payment["gift_name"]
    
    del pending_payments[order_id]
    
    try:
        await bot.send_message(
            user_id,
            f"✅ <b>Подарок вручён!</b>\n\n"
            f"🎁 {gift_name}\n"
            f"📝 Заказ: <code>{order_id}</code>\n\n"
            f"Спасибо за поддержку! ❤️\n"
            f"Твой подарок уже у стримерши!",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")
    
    admin_msg = await message.answer(f"✅ Подарок «{gift_name}» вручён пользователю!")
    asyncio.create_task(delete_message_after_delay(admin_msg, 30))


@router.message(Command("decline"))
async def decline_payment(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только администраторы могут использовать эту команду.")
        return
    
    text = message.text
    if " " in text:
        order_id = text.split()[1]
    else:
        order_id = text.replace("/decline_", "")
    
    if order_id not in pending_payments:
        await message.answer("❌ Заказ не найден")
        return
    
    payment = pending_payments[order_id]
    user_id = payment["user_id"]
    gift_name = payment["gift_name"]
    
    del pending_payments[order_id]
    
    try:
        await bot.send_message(
            user_id,
            f"❌ <b>Оплата отклонена</b>\n\n"
            f"🎁 Подарок: {gift_name}\n"
            f"📝 Заказ: <code>{order_id}</code>\n\n"
            f"⚠️ Если вы оплатили, свяжитесь с администратором.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")
    
    admin_msg = await message.answer(f"❌ Платёж отклонён")
    asyncio.create_task(delete_message_after_delay(admin_msg, 30))


@router.message(Command("payments"))
async def cmd_payments(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только администраторы могут использовать эту команду.")
        return
    
    if not pending_payments:
        msg = await message.answer("📋 Нет ожидающих платежей.")
        asyncio.create_task(delete_message_after_delay(msg, 30))
        return
    
    text = "📋 <b>Ожидающие платежи:</b>\n\n"
    for order_id, payment in pending_payments.items():
        text += f"• <code>{order_id}</code> | {payment['username'] or payment['user_id']} | {payment['gift_name']} | {payment['amount']} ₽\n"
    
    msg = await message.answer(text, parse_mode="HTML")
    asyncio.create_task(delete_message_after_delay(msg, 60))
