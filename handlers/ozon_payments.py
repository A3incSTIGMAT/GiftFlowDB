import logging
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import re

from database import add_transaction, get_gift_by_id, update_top_heroes, get_top_heroes, register_user
from keyboards import get_payment_details_keyboard, get_back_to_admin_keyboard, get_main_keyboard
from config import SUPER_ADMIN_ID, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

# ============ FSM СОСТОЯНИЯ ДЛЯ ОПЛАТЫ ============

class PaymentStates(StatesGroup):
    waiting_for_payment_confirmation = State()
    waiting_for_sbp_screenshot = State()


# ============ РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ ============

PAYMENT_DETAILS = {
    "card": "💳 <b>Оплата картой</b>\n\n"
            "Карта: <code>2204 3210 4743 4436</code>\n"
            "Получатель: Александр Б.\n\n"
            "💰 <i>После перевода нажми «Я оплатил(а)»</i>",
    
    "sbp": "📱 <b>Оплата по СБП / QR-код</b>\n\n"
           "📞 Номер телефона: <code>+7 995 253-89-15</code>\n"
           "🏦 Банк: Озон Банк\n\n"
           "💡 <i>Можно оплатить через любой банк по СБП</i>\n\n"
           "💰 <i>После оплаты нажми «Я оплатил(а)»</i>",
    
    "qr": "📱 <b>QR-код для оплаты</b>\n\n"
          "Отсканируйте QR-код в приложении любого банка:\n"
          "👉 <a href='https://qr.nspk.ru/...'>Ссылка на QR-код</a>\n\n"
          "💰 <i>После оплаты нажми «Я оплатил(а)»</i>"
}


# ============ ОБРАБОТЧИКИ ОПЛАТЫ ============

@router.callback_query(lambda c: c.data and c.data.startswith("pay_card_"))
async def pay_by_card(callback: types.CallbackQuery, state: FSMContext):
    """Оплата картой"""
    gift_id = int(callback.data.split("_")[2])
    
    gift = await get_gift_by_id(gift_id)
    if not gift:
        await callback.answer("Подарок не найден!", show_alert=True)
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        gift_id=gift_id,
        gift_name=gift['name'],
        gift_price=gift['price'],
        payment_method="card"
    )
    
    text = (
        f"{gift['icon']} <b>{gift['name']}</b>\n\n"
        f"💰 Сумма: <b>{gift['price']}₽</b>\n\n"
        f"{PAYMENT_DETAILS['card']}\n\n"
        f"⚠️ <i>Обязательно укажите в комментарии к платежу свой Telegram ID: <code>{callback.from_user.id}</code></i>"
    )
    
    keyboard = get_payment_details_keyboard(gift_id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("pay_sbp_"))
async def pay_by_sbp(callback: types.CallbackQuery, state: FSMContext):
    """Оплата по СБП"""
    gift_id = int(callback.data.split("_")[2])
    
    gift = await get_gift_by_id(gift_id)
    if not gift:
        await callback.answer("Подарок не найден!", show_alert=True)
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        gift_id=gift_id,
        gift_name=gift['name'],
        gift_price=gift['price'],
        payment_method="sbp"
    )
    
    text = (
        f"{gift['icon']} <b>{gift['name']}</b>\n\n"
        f"💰 Сумма: <b>{gift['price']}₽</b>\n\n"
        f"{PAYMENT_DETAILS['sbp']}\n\n"
        f"⚠️ <i>Обязательно укажите в комментарии к платежу свой Telegram ID: <code>{callback.from_user.id}</code></i>"
    )
    
    keyboard = get_payment_details_keyboard(gift_id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("confirm_payment_"))
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь подтверждает оплату"""
    gift_id = int(callback.data.split("_")[2])
    
    # Получаем данные из состояния
    data = await state.get_data()
    gift_name = data.get('gift_name', f"Подарок #{gift_id}")
    gift_price = data.get('gift_price', 0)
    payment_method = data.get('payment_method', 'unknown')
    
    # Регистрируем пользователя
    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    last_name = callback.from_user.last_name
    
    await register_user(user_id, username, first_name, last_name)
    
    # Создаём транзакцию
    transaction_id = await add_transaction(
        user_id=user_id,
        gift_id=gift_id,
        amount=gift_price,
        payment_method=payment_method
    )
    
    # Уведомляем админов о новом заказе
    admin_text = (
        f"🆕 <b>Новый заказ!</b>\n\n"
        f"📦 Подарок: {gift_name}\n"
        f"💰 Сумма: {gift_price}₽\n"
        f"👤 Пользователь: @{username or 'нет юзернейма'} ({user_id})\n"
        f"💳 Способ: {payment_method}\n"
        f"🆔 Заказ: #{transaction_id}\n\n"
        f"✅ <i>Подтвердите оплату в админ-панели</i>"
    )
    
    # Отправляем уведомление супер-админу и менеджеру
    try:
        await callback.bot.send_message(SUPER_ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление супер-админу: {e}")
    
    try:
        await callback.bot.send_message(SUPPORT_ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление менеджеру: {e}")
    
    # Ответ пользователю
    await callback.message.edit_text(
        f"✅ <b>Спасибо за поддержку!</b>\n\n"
        f"Ваш заказ #{transaction_id} принят.\n"
        f"🎁 {gift_name} — {gift_price}₽\n\n"
        f"⏳ <i>Менеджер проверит оплату в ближайшее время.</i>\n"
        f"💰 <i>После подтверждения вы попадёте в топ героев!</i>\n\n"
        f"🔙 Вернуться в главное меню: /start",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()
    await callback.answer("Заказ оформлен! Ожидайте подтверждения.")


# ============ АДМИН ФУНКЦИИ ДЛЯ ПОДТВЕРЖДЕНИЯ ОПЛАТ ============

@router.message(lambda message: message.text == "📦 Управление заказами")
async def manage_orders(message: types.Message):
    """Показать список ожидающих заказов (админка)"""
    from database import get_pending_transactions
    
    user_id = message.from_user.id
    from database import is_admin
    if not await is_admin(user_id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    transactions = await get_pending_transactions(limit=20)
    
    if not transactions:
        await message.answer(
            "📦 <b>Нет ожидающих заказов</b>\n\n"
            "Все заказы обработаны.",
            parse_mode="HTML"
        )
        return
    
    text = "📦 <b>Ожидают подтверждения:</b>\n\n"
    
    for t in transactions[:10]:
        text += (
            f"┌ <b>Заказ #{t['id']}</b>\n"
            f"├ 🎁 {t['gift_name']}\n"
            f"├ 💰 {t['amount']}₽\n"
            f"├ 👤 @{t.get('username') or t['user_id']}\n"
            f"├ 💳 {t.get('payment_method', 'не указан')}\n"
            f"├ 🕐 {t['created_at'][:16]}\n"
            f"└ ✅ <code>/approve {t['id']}</code> — подтвердить\n\n"
        )
    
    text += "\n💡 <i>Используй команду /approve [номер_заказа] для подтверждения</i>"
    
    await message.answer(text, parse_mode="HTML")


@router.message(lambda message: message.text and message.text.startswith("/approve"))
async def approve_order(message: types.Message):
    """Подтверждение заказа: /approve 123"""
    from database import update_transaction_status, get_pending_transactions, get_all_transactions
    
    user_id = message.from_user.id
    from database import is_admin
    if not await is_admin(user_id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    # Парсим ID заказа
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(
            "❌ Неправильный формат.\n"
            "Используй: <code>/approve 123</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        transaction_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID заказа должен быть числом.")
        return
    
    # Получаем информацию о заказе
    transactions = await get_all_transactions(limit=100)
    transaction = next((t for t in transactions if t['id'] == transaction_id), None)
    
    if not transaction:
        await message.answer(f"❌ Заказ #{transaction_id} не найден.")
        return
    
    if transaction['status'] == 'paid':
        await message.answer(f"✅ Заказ #{transaction_id} уже был подтверждён.")
        return
    
    # Обновляем статус
    await update_transaction_status(transaction_id, 'paid', confirmed_by=user_id)
    
    # Обновляем топ героев
    user_id_from_transaction = transaction['user_id']
    amount = transaction['amount']
    username = transaction.get('username')
    
    position = await update_top_heroes(user_id_from_transaction, amount, username)
    
    # Уведомляем пользователя
    try:
        user_text = (
            f"✅ <b>Ваш заказ #{transaction_id} подтверждён!</b>\n\n"
            f"🎁 {transaction['gift_name']}\n"
            f"💰 Сумма: {amount}₽\n\n"
        )
        
        if position:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            medal = medals.get(position, "🎖️")
            user_text += f"{medal} <b>Вы в топ-{position} героев канала!</b>\n\n"
        
        user_text += "❤️ <i>Спасибо за поддержку Ланы!</i>"
        
        await message.bot.send_message(user_id_from_transaction, user_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление пользователю: {e}")
    
    # Уведомление в канал, если донат крупный
    if amount >= 5000:
        channel_text = (
            f"🎉 <b>Новый донат!</b>\n\n"
            f"@{username or 'Аноним'} подарил(а) {transaction['gift_name']} на {amount}₽\n"
            f"❤️ <i>Спасибо за поддержку!</i>"
        )
        try:
            from config import CHANNEL_ID
            await message.bot.send_message(CHANNEL_ID, channel_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление в канал: {e}")
    
    # Ответ админу
    await message.answer(
        f"✅ Заказ #{transaction_id} подтверждён!\n"
        f"Пользователь уведомлён.\n"
        f"Топ героев обновлён.",
        parse_mode="HTML"
    )


@router.message(lambda message: message.text == "/help_payment")
async def payment_help(message: types.Message):
    """Помощь по оплате"""
    text = (
        "💳 <b>Как оплатить подарок?</b>\n\n"
        "1. Выбери подарок в «🎁 Каталог подарков»\n"
        "2. Нажми «Оплатить картой» или «СБП/QR-код»\n"
        "3. Переведи сумму на указанные реквизиты\n"
        "4. <b>Обязательно укажи в комментарии свой Telegram ID</b>\n"
        "5. Нажми «Я оплатил(а)»\n"
        "6. Дождись подтверждения от менеджера\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Комиссию за перевод оплачиваешь ты\n"
        "• После подтверждения ты попадёшь в топ героев\n"
        "• По всем вопросам пиши @lanatwitchh"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(lambda message: message.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    """Показать статистику (админка)"""
    from database import get_stats, is_admin, get_pending_transactions, get_top_heroes
    
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ У вас нет прав доступа.")
        return
    
    stats = await get_stats()
    pending = await get_pending_transactions(limit=1)
    top_heroes = await get_top_heroes(limit=3)
    
    text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b> {stats.get('total_users', 0)}\n"
        f"🎁 <b>Всего донатов:</b> {stats.get('total_donations', 0)}\n"
        f"💰 <b>Общая сумма:</b> {stats.get('total_amount', 0):,}₽\n"
        f"📅 <b>За этот месяц:</b> {stats.get('month_amount', 0):,}₽\n"
        f"⏳ <b>Ожидают:</b> {len(pending)} заказов\n\n"
    )
    
    if top_heroes:
        text += "🏆 <b>Топ-3 героев:</b>\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, hero in enumerate(top_heroes[:3]):
            username = hero.get('username') or f"user_{hero['user_id']}"
            text += f"{medals[i]} {username} — {hero['total_amount']:,}₽\n"
    
    text += f"\n📊 <i>Обновлено: {stats.get('updated_at', datetime.now()).strftime('%d.%m.%Y %H:%M')}</i>"
    
    await message.answer(text, parse_mode="HTML")
