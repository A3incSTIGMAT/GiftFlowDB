import logging
from aiogram import Router, types, F
from database import get_gift_by_id, add_transaction, get_all_gifts
from keyboards import get_gift_detail_keyboard, get_gifts_keyboard
from donatepay import create_donatepay_invoice
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
    
    await callback.message.edit_text(
        f"{icon} <b>{gift['name']}</b>\n\n"
        f"💰 Цена: {gift['price']}₽\n"
        f"📝 {gift.get('description', 'Поддержи Лану!')}\n\n"
        f"Нажми кнопку для оплаты:\n\n"
        f"💡 <i>Обратите внимание: это добровольное пожертвование. "
        f"Вы не покупаете товар, а выражаете поддержку стримеру.</i>",
        parse_mode="HTML",
        reply_markup=await get_gift_detail_keyboard(gift_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_"))
async def pay_gift(callback: types.CallbackQuery):
    """Обработка оплаты подарка"""
    gift_id = int(callback.data.split("_")[1])
    gift = await get_gift_by_id(gift_id)
    
    if not gift:
        await callback.answer("❌ Подарок не найден")
        return
    
    # Показываем пользователю, что идёт создание счёта
    processing_msg = await callback.message.answer(
        "⏳ <b>Создаём счёт...</b>\n\n"
        "Пожалуйста, подожди несколько секунд.",
        parse_mode="HTML"
    )
    
    # Создаём счёт в DonatePay
    payment_url = await create_donatepay_invoice(
        amount=gift['price'],
        description=gift['name'],
        user_id=callback.from_user.id
    )
    
    # Удаляем сообщение о загрузке
    await processing_msg.delete()
    
    if payment_url:
        # Сохраняем транзакцию
        await add_transaction(
            callback.from_user.id,
            callback.from_user.username,
            gift['id'],
            gift['name'],
            gift['price'],
            None
        )
        
        # Рассчитываем распределение
        amount = gift['price']
        lana_share = amount * PROFIT_SPLIT['lana']
        admin_share = amount * PROFIT_SPLIT['admin']
        dev_share = amount * PROFIT_SPLIT['development']
        tax_share = amount * PROFIT_SPLIT['tax']
        
        # Юридическое уведомление
        legal_notice = (
            "💡 <b>Юридическая информация</b>\n"
            "Данный платёж является <b>добровольным пожертвованием (дарением)</b> "
            "в поддержку творческой деятельности стримера.\n\n"
            "📜 <b>Правовое основание:</b> ст. 572 ГК РФ (договор дарения), "
            "п. 18.1 ст. 217 НК РФ (освобождение от налогообложения).\n\n"
            "Вы не приобретаете товар, работу или услугу, а выражаете "
            "благодарность и поддержку."
        )
        
        await callback.message.edit_text(
            f"✅ <b>Счёт создан!</b>\n\n"
            f"🎁 Подарок: {gift['name']}\n"
            f"💰 Сумма: {amount}₽\n\n"
            f"🔗 <a href='{payment_url}'>Нажми сюда для оплаты</a>\n\n"
            f"После оплаты подарок автоматически придёт на стрим!\n\n"
            f"📈 <b>Распределение доната:</b>\n"
            f"👤 Лана (47%): {int(lana_share)}₽\n"
            f"👤 Админ (28%): {int(admin_share)}₽\n"
            f"🚀 Развитие (19%): {int(dev_share)}₽\n"
            f"📋 Налог (6%): {int(tax_share)}₽\n\n"
            f"{legal_notice}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        
        # Уведомляем админов
        from aiogram import Bot
        from config import BOT_TOKEN
        
        bot = Bot(token=BOT_TOKEN)
        for admin_id in ADMIN_IDS:
            await bot.send_message(
                admin_id,
                f"💰 <b>Новый заказ!</b>\n\n"
                f"👤 От: @{callback.from_user.username or 'без username'}\n"
                f"🆔 ID: {callback.from_user.id}\n"
                f"🎁 Подарок: {gift['name']}\n"
                f"💵 Сумма: {amount}₽\n\n"
                f"📈 <b>Распределение:</b>\n"
                f"👤 Лана (47%): {int(lana_share)}₽\n"
                f"👤 Админ (28%): {int(admin_share)}₽\n"
                f"🚀 Развитие (19%): {int(dev_share)}₽\n"
                f"📋 Налог (6%): {int(tax_share)}₽",
                parse_mode="HTML"
            )
        
    else:
        await callback.message.answer(
            "❌ <b>Ошибка создания счета</b>\n\n"
            "Не удалось подключиться к платежной системе DonatePay.\n\n"
            "🔧 <b>Возможные причины:</b>\n"
            "• Технические работы на DonatePay\n"
            "• Проблемы с API ключом\n"
            "• Неверный кошелёк\n\n"
            "💡 <b>Что делать?</b>\n"
            "1️⃣ Попробуй позже\n"
            "2️⃣ Проверь, что на DonatePay достаточно средств\n"
            "3️⃣ Напиши администратору, если проблема повторяется\n\n"
            "📞 <b>Альтернативный способ:</b>\n"
            "Можно перевести донат напрямую по реквизитам, которые пришлёт админ.",
            parse_mode="HTML"
        )
    
    await callback.answer()


@router.message(lambda message: message.text and any(word in message.text.lower() for word in ["подарок", "донат", "оплата", "как оплатить"]))
async def handle_gift_question(message: types.Message):
    """Обработка вопросов о подарках"""
    if message.from_user.id in ADMIN_IDS:
        return
    
    await message.answer(
        "🎁 <b>О подарках и донатах</b>\n\n"
        "Все подарки — это добровольные пожертвования в поддержку стримера.\n\n"
        "📜 <b>Как это работает:</b>\n"
        "1️⃣ Ты выбираешь подарок в каталоге\n"
        "2️⃣ Нажимаешь «Оплатить» — создаётся счёт\n"
        "3️⃣ Переходишь по ссылке на DonatePay\n"
        "4️⃣ Совершаешь платёж (сумма фиксированная)\n"
        "5️⃣ Подарок отображается в эфире\n\n"
        "💡 <b>Важно:</b> Это не покупка товара, а выражение поддержки. "
        "Все платежи являются добровольными пожертвованиями.\n\n"
        "🔒 <b>Безопасность:</b>\n"
        "Все платежи проходят через защищённый шлюз DonatePay.\n"
        "Мы не храним данные твоих карт.\n\n"
        "📞 <b>Проблемы с оплатой?</b>\n"
        "Напиши администратору — ответим в ближайшее время.\n\n"
        "Спасибо за поддержку! ❤️",
        parse_mode="HTML"
    )
