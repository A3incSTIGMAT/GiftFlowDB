import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_all_gifts, create_order, get_gift_by_id
from config import OZON_CARD_LAST, OZON_BANK_NAME, OZON_RECEIVER, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

# ============ СОСТОЯНИЯ ============

class PaymentStates(StatesGroup):
    waiting_for_receipt = State()

# ============ КЛАВИАТУРА ДЛЯ КАТАЛОГА ============

def get_gifts_keyboard(gifts):
    """Клавиатура для каталога подарков"""
    keyboard = []
    row = []
    for i, gift in enumerate(gifts, 1):
        row.append(InlineKeyboardButton(
            text=f"{gift['icon']} {gift['name']} - {gift['price']}₽",
            callback_data=f"gift_{gift['id']}"
        ))
        if i % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ============ ПОКАЗ КАТАЛОГА ============

async def show_gifts_catalog(message: types.Message):
    """Показать каталог подарков"""
    gifts = get_all_gifts()
    
    if not gifts:
        await message.answer(
            "🎁 <b>Каталог подарков пока пуст</b>\n\nЗагляни позже!",
            parse_mode="HTML"
        )
        return
    
    text = "🎁 <b>Выбери подарок для Ланы:</b>"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_gifts_keyboard(gifts)
    )

# ============ ОБРАБОТКА ВЫБОРА ПОДАРКА ============

@router.callback_query(lambda c: c.data and c.data.startswith("gift_"))
async def gift_selected(callback: types.CallbackQuery):
    """Обработка выбора подарка"""
    try:
        gift_id = int(callback.data.split("_")[1])
        gift = get_gift_by_id(gift_id)
        
        if not gift:
            await callback.answer("Подарок не найден!", show_alert=True)
            return
        
        # Создаём заказ
        order_id = create_order(
            user_id=callback.from_user.id,
            gift_id=gift_id,
            amount=gift['price'],
            username=callback.from_user.username
        )
        
        # Новая ссылка для оплаты
        user_id = callback.from_user.id
        payment_link = f"https://finance.ozon.ru/apps/sbp/ozonbankpay/019d71b4-afcd-739d-8e57-8ef0e95d4372?comment={user_id}"
        
        # Текст для оплаты
        payment_text = (
            f"🎁 <b>{gift['icon']} {gift['name']}</b>\n"
            f"💰 Сумма: <b>{gift['price']:,}₽</b>\n\n"
            f"💳 <b>Оплата по СБП</b>\n"
            f"🏦 Банк: {OZON_BANK_NAME}\n\n"
            f"📝 <b>Укажите в комментарии Telegram ID:</b> {user_id}\n\n"
            f"📲 <b>После оплаты отправьте чек (скриншот)</b>\n\n"
            f"⚠️ <i>Важно: Донаты являются добровольным пожертвованием и не возвращаются.</i>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить по ссылке", url=payment_link)],
            [InlineKeyboardButton(text="📸 Отправить чек об оплате", callback_data=f"paid_{order_id}")],
            [InlineKeyboardButton(text="🔙 Назад к подаркам", callback_data="back_to_gifts_catalog")]
        ])
        
        await callback.message.delete()
        await callback.message.answer(
            payment_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка gift_selected: {e}")
        await callback.answer("Ошибка, попробуйте позже", show_alert=True)

# ============ ОБРАБОТКА ОПЛАТЫ (отправка чека) ============

@router.callback_query(lambda c: c.data and c.data.startswith("paid_"))
async def payment_paid(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь нажал «Отправить чек об оплате»"""
    try:
        order_id = int(callback.data.split("_")[1])
        
        await state.update_data(order_id=order_id)
        await state.set_state(PaymentStates.waiting_for_receipt)
        
        await callback.message.edit_text(
            f"📸 <b>Отправьте скриншот чека</b>\n\n"
            f"Заказ #{order_id}\n\n"
            f"Отправьте фото чека одним сообщением.\n"
            f"После проверки я подтвержу подарок.\n\n"
            f"❌ Отмена - /cancel",
            parse_mode="HTML"
        )
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка payment_paid: {e}")
        await callback.answer("Ошибка, попробуйте снова", show_alert=True)

# ============ ПОЛУЧЕНИЕ ЧЕКА ============

@router.message(PaymentStates.waiting_for_receipt, lambda message: message.photo)
async def receive_receipt(message: types.Message, state: FSMContext):
    """Получение скриншота чека"""
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        await message.answer(
            "❌ Ошибка: заказ не найден. Начните оплату заново.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    photo = message.photo[-1]
    
    # Кнопки для админа
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПОДТВЕРДИТЬ", callback_data=f"approve_{order_id}")],
        [InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"reject_{order_id}")]
    ])
    
    admin_text = (
        f"🧾 <b>НОВЫЙ ЧЕК!</b>\n\n"
        f"🆔 Заказ: #{order_id}\n"
        f"👤 Пользователь: @{message.from_user.username or message.from_user.first_name}\n"
        f"🆔 ID: {message.from_user.id}\n"
    )
    
    await message.bot.send_photo(
        SUPPORT_ADMIN_ID,
        photo=photo.file_id,
        caption=admin_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    # ========== ПОДТВЕРЖДЕНИЕ ПОЛЬЗОВАТЕЛЮ, ЧТО ЧЕК ПОЛУЧЕН ==========
    await message.answer(
        "✅ <b>Чек получен!</b>\n\n"
        "❤️ Спасибо, что поддерживаешь меня!\n"
        "Я проверю чек в ближайшее время и напишу тебе.\n\n"
        "Обычно это занимает несколько минут.\n"
        "С любовью, <b>Лана</b> 💫",
        parse_mode="HTML"
    )
    await state.clear()

@router.message(PaymentStates.waiting_for_receipt)
async def invalid_receipt(message: types.Message):
    """Если прислали не фото"""
    await message.answer(
        "❌ Пожалуйста, отправьте <b>ФОТО чека</b>.\n\n"
        "Сделайте скриншот перевода из банка и отправьте сюда.\n\n"
        "❌ Отмена - /cancel",
        parse_mode="HTML"
    )

# ============ ВОЗВРАТ В КАТАЛОГ ============

@router.callback_query(lambda c: c.data == "back_to_gifts_catalog")
async def back_to_gifts_catalog(callback: types.CallbackQuery):
    """Возврат в каталог подарков"""
    await callback.message.delete()
    await show_gifts_catalog(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    from handlers.start import start_command
    await state.clear()
    await callback.message.delete()
    
    class FakeMessage:
        def __init__(self, from_user, chat, bot):
            self.from_user = from_user
            self.chat = chat
            self.bot = bot
            self.text = "/start"
    
    fake_msg = FakeMessage(callback.from_user, callback.message.chat, callback.bot)
    await start_command(fake_msg, state)
    await callback.answer()
