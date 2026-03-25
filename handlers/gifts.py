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
    """Показать каталог подарков"""
    gifts = await get_all_gifts()
    if not gifts:
        await callback.message.edit_text(
            "🎁 <b>Каталог подарков</b>\n\n"
            "Подарки временно недоступны. Попробуй позже.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🎁 <b>Выбери подарок для Ланы:</b>\n\n"
        "После оплаты подарок появится на стриме!\n\n"
        "💳 <b>Оплата через Telegram Stars</b>\n"
        "• Карты любых банков\n"
        "• СБП\n"
        "• Быстро и безопасно\n\n"
        "💡 <i>Все платежи являются добровольными пожертвованиями</i>",
        parse_mode="HTML",
        reply_markup=await get_gifts_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gift_"))
async def gift_detail(callback: types.CallbackQuery):
    """Показать детали подарка"""
    gift_id = int(callback.data.split("_")[1])
    gift = await get_gift_by_id(gift_id)
    
    if not gift:
        await callback.answer("❌ Подарок не найден")
        return
    
    icon = gift.get('icon', '🎁')
    
    # Конвертируем рубли в Stars (1 Star ≈ 0.01 USD, примерно 0.7-0.8 руб)
    # Для простоты: 1 Star = 0.75 руб, но Telegram сам конвертирует
    # Лучше оставить рубли, Stars умеют работать с рублями
    star_price = gift['price']
    
    await callback.message.edit_text(
        f"{icon} <b>{gift['name']}</b>\n\n"
        f"💰 Цена: {gift['price']}₽\n"
        f"⭐ Или {star_price} Stars\n\n"
        f"📝 {gift.get('description', 'Поддержи Лану!')}\n\n"
        f"💳 <b>Как оплатить:</b>\n"
        f"1️⃣ Нажми кнопку «Оплатить»\n"
        f"2️⃣ Выбери способ оплаты (карта/СБП)\n"
        f"3️⃣ Подтверди платеж\n"
        f"4️⃣ Подарок придёт автоматически\n\n"
        f"💡 <i>Это добровольное пожертвование. "
        f"Вы не покупаете товар, а выражаете поддержку стримеру.</i>",
        parse_mode="HTML",
        reply_markup=await get_gift_detail_keyboard(gift_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_"))
async def pay_gift(callback: types.CallbackQuery):
    """Создание счёта через Telegram Stars"""
    gift_id = int(callback.data.split("_")[1])
    gift = await get_gift_by_id(gift_id)
    
    if not gift:
        await callback.answer("❌ Подарок не найден")
        return
    
    from aiogram import Bot
    from config import BOT_TOKEN
    
    bot = Bot(token=BOT_TOKEN)
    
    # Цена в рублях (Telegram сам конвертирует в Stars)
    price_in_rub = gift['price']
    
    try:
        # Создаём счёт через Stars
        # provider_token оставляем пустым для Stars
        invoice = await bot.create_invoice_link(
            title=f"🎁 {gift['name']}",
            description=gift.get('description', 'Подарок стримерше'),
            payload=f"gift_{gift_id}_{callback.from_user.id}",
            provider_token="",  # Пустая строка для Stars
            currency="RUB",  # Telegram сам конвертирует в Stars
            prices=[
                LabeledPrice(label=gift['name'], amount=price_in_rub * 100)  # В копейках
            ],
            start_parameter="donate",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        
        # Показываем пользователю ссылку на оплату
        await callback.message.edit_text(
            f"✅ <b>Счёт создан!</b>\n\n"
            f"🎁 Подарок: {gift['name']}\n"
            f"💰 Сумма: {price_in_rub}₽\n\n"
            f"🔗 <a href='{invoice}'>Нажми сюда для оплаты</a>\n\n"
            f"💳 <b>Как оплатить:</b>\n"
            f"• Банковская карта (Visa/Mastercard/Мир)\n"
            f"• СБП (Система быстрых платежей)\n"
            f"• Баланс Telegram Stars\n\n"
            f"После оплаты подарок автоматически придёт на стрим!\n\n"
            f"📈 <b>Распределение доната:</b>\n"
            f"👤 Лана (47%): {int(price_in_rub * PROFIT_SPLIT['lana'])}₽\n"
            f"👤 Админ (28%): {int(price_in_rub * PROFIT_SPLIT['admin'])}₽\n"
            f"🚀 Развитие (19%): {int(price_in_rub * PROFIT_SPLIT['development'])}₽\n"
            f"📋 Налог (6%): {int(price_in_rub * PROFIT_SPLIT['tax'])}₽\n\n"
            f"💡 <b>Юридическая информация</b>\n"
            f"Данный платёж является добровольным пожертвованием (дарением) "
            f"в поддержку творческой деятельности стримера.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"💰 <b>Новый заказ!</b>\n\n"
                f"👤 От: @{callback.from_user.username or 'без username'}\n"
                f"🆔 ID: {callback.from_user.id}\n"
                f"🎁 Подарок: {gift['name']}\n"
                f"💵 Сумма: {price_in_rub}₽\n\n"
                f"⏳ Ожидаем оплату через Stars",
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Ошибка создания счёта Stars: {e}")
        await callback.message.answer(
            "❌ <b>Ошибка создания счета</b>\n\n"
            "Не удалось подключиться к платежной системе Telegram Stars.\n\n"
            "🔧 <b>Что делать?</b>\n"
            "1️⃣ Попробуй позже\n"
            "2️⃣ Напиши администратору, если проблема повторяется\n\n"
            "📞 <b>Альтернативный способ:</b>\n"
            "Можно перевести донат напрямую по реквизитам, которые пришлёт админ.",
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    """Подтверждение оплаты (обязательный хендлер)"""
    await pre_checkout_query.answer(ok=True)
    logger.info(f"Pre-checkout для {pre_checkout_query.from_user.id}")


@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Обработка успешной оплаты"""
    payment = message.successful_payment
    payload = payment.invoice_payload  # gift_id_userid
    star_amount = payment.total_amount  # сумма в копейках (рубли)
    
    # Парсим payload
    try:
        parts = payload.split("_")
        if len(parts) >= 2:
            gift_id = int(parts[1])
            user_id = int(parts[2]) if len(parts) > 2 else message.from_user.id
            
            # Получаем подарок
            gift = await get_gift_by_id(gift_id)
            if gift:
                # Сохраняем транзакцию
                await add_transaction(
                    message.from_user.id,
                    message.from_user.username,
                    gift_id,
                    gift['name'],
                    gift['price'],
                    payment.telegram_payment_charge_id
                )
                
                # Благодарственное сообщение
                await message.answer(
                    f"✅ <b>Спасибо за поддержку!</b>\n\n"
                    f"🎁 Подарок: {gift['name']}\n"
                    f"💰 Сумма: {gift['price']}₽\n\n"
                    f"Твой подарок уже вручён стримерше! "
                    f"Следи за эфиром — возможно, он появится на стриме.\n\n"
                    f"🙏 Спасибо, что поддерживаешь Лану!",
                    parse_mode="HTML"
                )
                
                # Уведомляем админов
                from aiogram import Bot
                from config import BOT_TOKEN, PROFIT_SPLIT
                
                bot = Bot(token=BOT_TOKEN)
                amount = gift['price']
                lana_share = amount * PROFIT_SPLIT['lana']
                admin_share = amount * PROFIT_SPLIT['admin']
                dev_share = amount * PROFIT_SPLIT['development']
                tax_share = amount * PROFIT_SPLIT['tax']
                
                for admin_id in ADMIN_IDS:
                    await bot.send_message(
                        admin_id,
                        f"✅ <b>Оплата получена!</b>\n\n"
                        f"👤 От: @{message.from_user.username or 'без username'}\n"
                        f"🆔 ID: {message.from_user.id}\n"
                        f"🎁 Подарок: {gift['name']}\n"
                        f"💵 Сумма: {amount}₽\n\n"
                        f"📈 <b>Распределение:</b>\n"
                        f"👤 Лана (47%): {int(lana_share)}₽\n"
                        f"👤 Админ (28%): {int(admin_share)}₽\n"
                        f"🚀 Развитие (19%): {int(dev_share)}₽\n"
                        f"📋 Налог (6%): {int(tax_share)}₽",
                        parse_mode="HTML"
                    )
                
                logger.info(f"Успешная оплата: {gift['name']} от {message.from_user.id}")
                
    except Exception as e:
        logger.error(f"Ошибка обработки успешной оплаты: {e}")
        await message.answer(
            "✅ <b>Оплата прошла успешно!</b>\n\n"
            "Спасибо за поддержку! Подарок будет вручён в ближайшее время.\n\n"
            "Если возникнут вопросы — напиши администратору.",
            parse_mode="HTML"
        )


@router.message(lambda message: message.text and any(word in message.text.lower() for word in ["подарок", "донат", "оплата", "как оплатить", "stars"]))
async def handle_gift_question(message: types.Message):
    """Обработка вопросов о подарках"""
    if message.from_user.id in ADMIN_IDS:
        return
    
    await message.answer(
        "🎁 <b>О подарках и донатах</b>\n\n"
        "Все подарки — это добровольные пожертвования в поддержку стримера.\n\n"
        "📜 <b>Как это работает:</b>\n"
        "1️⃣ Ты выбираешь подарок в каталоге\n"
        "2️⃣ Нажимаешь «Оплатить» — создаётся ссылка\n"
        "3️⃣ Переходишь по ссылке (откроется Telegram)\n"
        "4️⃣ Выбираешь способ оплаты (карта/СБП/Stars)\n"
        "5️⃣ Подтверждаешь платеж\n"
        "6️⃣ Подарок автоматически вручается стримерше\n\n"
        "💳 <b>Способы оплаты:</b>\n"
        "• Банковская карта (Visa/Mastercard/Мир)\n"
        "• СБП (Система быстрых платежей)\n"
        "• Telegram Stars (если есть на балансе)\n\n"
        "💡 <b>Важно:</b> Это не покупка товара, а выражение поддержки. "
        "Все платежи являются добровольными пожертвованиями.\n\n"
        "🔒 <b>Безопасность:</b>\n"
        "Все платежи проходят через защищённую систему Telegram.\n"
        "Мы не храним данные твоих карт.\n\n"
        "📞 <b>Вопросы?</b> Напиши администратору — ответим в ближайшее время.\n\n"
        "Спасибо за поддержку! ❤️",
        parse_mode="HTML"
    )
