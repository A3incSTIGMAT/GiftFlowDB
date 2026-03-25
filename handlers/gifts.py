import logging
from aiogram import Router, types, F
from aiogram.types import LabeledPrice
from database import get_gift_by_id, add_transaction, get_all_gifts
from keyboards import get_gift_detail_keyboard, get_gifts_keyboard
from config import ADMIN_IDS, PROFIT_SPLIT

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "show_gifts")
async def show_gifts(callback: types.CallbackQuery):
    gifts = await get_all_gifts()
    if not gifts:
        await callback.message.edit_text(
            "🎁 <b>Каталог подарков</b>\n\nПодарки временно недоступны.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🎁 <b>Выбери подарок для Ланы:</b>\n\n"
        "После оплаты подарок появится на стриме!\n\n"
        "💳 <b>Оплата через Telegram Stars</b>\n"
        "• Карты любых банков\n• СБП\n• Быстро и безопасно\n\n"
        "💡 <i>Все платежи — добровольные пожертвования</i>",
        parse_mode="HTML",
        reply_markup=await get_gifts_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gift_"))
async def gift_detail(callback: types.CallbackQuery):
    gift_id = int(callback.data.split("_")[1])
    gift = await get_gift_by_id(gift_id)
    
    if not gift:
        await callback.answer("❌ Подарок не найден")
        return
    
    icon = gift.get('icon', '🎁')
    
    await callback.message.edit_text(
        f"{icon} <b>{gift['name']}</b>\n\n"
        f"💰 Цена: {gift['price']}₽\n\n"
        f"📝 {gift.get('description', 'Поддержи Лану!')}\n\n"
        f"💳 <b>Как оплатить:</b>\n"
        f"1️⃣ Нажми кнопку «Оплатить»\n"
        f"2️⃣ Выбери способ оплаты (карта/СБП)\n"
        f"3️⃣ Подтверди платеж\n"
        f"4️⃣ Подарок придёт автоматически\n\n"
        f"💡 <i>Это добровольное пожертвование.</i>",
        parse_mode="HTML",
        reply_markup=await get_gift_detail_keyboard(gift_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_"))
async def pay_gift(callback: types.CallbackQuery):
    gift_id = int(callback.data.split("_")[1])
    gift = await get_gift_by_id(gift_id)
    
    if not gift:
        await callback.answer("❌ Подарок не найден")
        return
    
    from aiogram import Bot
    from config import BOT_TOKEN
    
    bot = Bot(token=BOT_TOKEN)
    price_in_rub = gift['price']
    
    try:
        invoice = await bot.create_invoice_link(
            title=f"🎁 {gift['name']}",
            description=gift.get('description', 'Подарок стримерше'),
            payload=f"gift_{gift_id}_{callback.from_user.id}",
            provider_token="",
            currency="RUB",
            prices=[LabeledPrice(label=gift['name'], amount=price_in_rub * 100)],
            start_parameter="donate"
        )
        
        await callback.message.edit_text(
            f"✅ <b>Счёт создан!</b>\n\n"
            f"🎁 Подарок: {gift['name']}\n"
            f"💰 Сумма: {price_in_rub}₽\n\n"
            f"🔗 <a href='{invoice}'>Нажми сюда для оплаты</a>\n\n"
            f"После оплаты подарок придёт автоматически!\n\n"
            f"📈 <b>Распределение:</b>\n"
            f"👤 Лана (47%): {int(price_in_rub * 0.47)}₽\n"
            f"👤 Админ (28%): {int(price_in_rub * 0.28)}₽\n"
            f"🚀 Развитие (19%): {int(price_in_rub * 0.19)}₽\n"
            f"📋 Налог (6%): {int(price_in_rub * 0.06)}₽",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"💰 <b>Новый заказ!</b>\n\n"
                f"👤 От: @{callback.from_user.username or 'без username'}\n"
                f"🎁 Подарок: {gift['name']}\n"
                f"💵 Сумма: {price_in_rub}₽",
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Stars error: {e}")
        await callback.message.answer(
            "❌ <b>Ошибка создания счета</b>\n\n"
            "Не удалось подключиться к Telegram Stars.\n\n"
            "🔧 Попробуй позже или напиши администратору.",
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    
    try:
        parts = payload.split("_")
        if len(parts) >= 2:
            gift_id = int(parts[1])
            gift = await get_gift_by_id(gift_id)
            if gift:
                await add_transaction(
                    message.from_user.id,
                    message.from_user.username,
                    gift_id,
                    gift['name'],
                    gift['price'],
                    payment.telegram_payment_charge_id
                )
                
                await message.answer(
                    f"✅ <b>Спасибо за поддержку!</b>\n\n"
                    f"🎁 Подарок: {gift['name']}\n"
                    f"💰 Сумма: {gift['price']}₽\n\n"
                    f"Твой подарок уже вручён стримерше!\n\n"
                    f"🙏 Спасибо!",
                    parse_mode="HTML"
                )
                
                for admin_id in ADMIN_IDS:
                    from aiogram import Bot
                    from config import BOT_TOKEN
                    bot = Bot(token=BOT_TOKEN)
                    await bot.send_message(
                        admin_id,
                        f"✅ <b>Оплата получена!</b>\n\n"
                        f"👤 От: @{message.from_user.username or 'без username'}\n"
                        f"🎁 Подарок: {gift['name']}\n"
                        f"💵 Сумма: {gift['price']}₽",
                        parse_mode="HTML"
                    )
                    
    except Exception as e:
        logger.error(f"Payment error: {e}")
        await message.answer("✅ Оплата прошла успешно! Спасибо!")
