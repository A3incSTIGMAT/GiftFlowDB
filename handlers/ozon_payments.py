import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import add_transaction, get_gift_by_id, update_top_heroes, register_user, is_admin, get_pending_transactions, get_all_transactions, update_transaction_status
from keyboards import get_payment_details_keyboard, get_main_keyboard
from config import SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, CHANNEL_ID, OZON_CARD_LAST, OZON_BANK_NAME, OZON_RECEIVER, OZON_SBP_QR_URL

logger = logging.getLogger(__name__)
router = Router()

class PaymentStates(StatesGroup):
    waiting_for_payment_confirmation = State()
    waiting_for_sbp_screenshot = State()

@router.callback_query(lambda c: c.data and c.data.startswith("pay_card_"))
async def pay_by_card(callback: types.CallbackQuery, state: FSMContext):
    gift_id = int(callback.data.split("_")[2])
    gift = await get_gift_by_id(gift_id)
    if not gift:
        await callback.answer("Подарок не найден!", show_alert=True)
        return
    
    await state.update_data(gift_id=gift_id, gift_name=gift['name'], gift_price=gift['price'], payment_method="card")
    
    # Данные из переменных окружения
    card_number = f"2204 3210 4743 {OZON_CARD_LAST}"
    
    text = (
        f"{gift['icon']} <b>{gift['name']}</b>\n\n"
        f"💰 Сумма: <b>{gift['price']}₽</b>\n\n"
        f"💳 <b>Оплата картой</b>\n\n"
        f"Карта: <code>{card_number}</code>\n"
        f"Получатель: {OZON_RECEIVER}\n\n"
        f"💰 <i>После перевода нажми «Я оплатил(а)»</i>\n\n"
        f"⚠️ <i>Укажите в комментарии Telegram ID: <code>{callback.from_user.id}</code></i>\n\n"
        f"❤️ <b>Важно:</b> Донаты являются добровольным пожертвованием и не возвращаются."
    )
    keyboard = get_payment_details_keyboard(gift_id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("pay_sbp_"))
async def pay_by_sbp(callback: types.CallbackQuery, state: FSMContext):
    gift_id = int(callback.data.split("_")[2])
    gift = await get_gift_by_id(gift_id)
    if not gift:
        await callback.answer("Подарок не найден!", show_alert=True)
        return
    
    await state.update_data(gift_id=gift_id, gift_name=gift['name'], gift_price=gift['price'], payment_method="sbp")
    
    # Данные из переменных окружения
    sbp_link = OZON_SBP_QR_URL
    if not sbp_link.startswith("https://"):
        sbp_link = f"https://finance.ozon.ru/apps/sbp/ozonbankpay/{OZON_SBP_QR_URL}"
    
    text = (
        f"{gift['icon']} <b>{gift['name']}</b>\n\n"
        f"💰 Сумма: <b>{gift['price']}₽</b>\n\n"
        f"📱 <b>Оплата по СБП / QR-код</b>\n\n"
        f"🏦 Банк: {OZON_BANK_NAME}\n"
        f"🔗 <b>Ссылка на оплату (любой банк, без комиссии):</b>\n"
        f"<code>{sbp_link}</code>\n\n"
        f"💰 <i>После оплаты нажми «Я оплатил(а)»</i>\n\n"
        f"⚠️ <i>Укажите в комментарии Telegram ID: <code>{callback.from_user.id}</code></i>\n\n"
        f"❤️ <b>Важно:</b> Донаты являются добровольным пожертвованием и не возвращаются."
    )
    keyboard = get_payment_details_keyboard(gift_id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(lambda c: c.data and c.data.startswith("confirm_payment_"))
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext):
    gift_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    gift_name = data.get('gift_name', f"Подарок #{gift_id}")
    gift_price = data.get('gift_price', 0)
    payment_method = data.get('payment_method', 'unknown')
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name
    
    await register_user(user_id, username, first_name)
    transaction_id = await add_transaction(user_id, gift_id, gift_price, payment_method)
    
    admin_text = (
        f"🆕 <b>Новый заказ!</b>\n\n"
        f"📦 Подарок: {gift_name}\n"
        f"💰 Сумма: {gift_price}₽\n"
        f"👤 Пользователь: @{username or 'нет'} ({user_id})\n"
        f"🆔 Заказ: #{transaction_id}"
    )
    
    try:
        await callback.bot.send_message(SUPER_ADMIN_ID, admin_text, parse_mode="HTML")
        if SUPPORT_ADMIN_ID and SUPPORT_ADMIN_ID != SUPER_ADMIN_ID:
            await callback.bot.send_message(SUPPORT_ADMIN_ID, admin_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка уведомления админов: {e}")
    
    await callback.message.edit_text(
        f"✅ <b>Спасибо за поддержку!</b>\n\n"
        f"Заказ #{transaction_id} принят.\n"
        f"🎁 {gift_name} — {gift_price}₽\n\n"
        f"⏳ Менеджер проверит оплату.\n"
        f"💰 После подтверждения вы попадёте в топ героев!\n\n"
        f"❤️ Донаты являются добровольным пожертвованием и не возвращаются.",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    await state.clear()
    await callback.answer("Заказ оформлен!")

# Остальные функции (manage_orders, approve_order, show_statistics) без изменений
