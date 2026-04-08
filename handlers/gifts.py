import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_all_gifts, create_order, get_gift_by_id
from config import OZON_CARD_LAST, OZON_BANK_NAME, OZON_RECEIVER

logger = logging.getLogger(__name__)
router = Router()

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
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ============ ПОКАЗ КАТАЛОГА ============

async def show_gifts_catalog(message: types.Message):
    """Показать каталог подарков"""
    gifts = await get_all_gifts()
    
    if not gifts:
        await message.answer(
            "🎁 <b>Каталог подарков пока пуст</b>\n\n"
            "Загляни позже!",
            parse_mode="HTML"
        )
        return
    
    text = "🎁 <b>Каталог подарков</b>\n\n"
    for gift in gifts:
        text += f"{gift['icon']} <b>{gift['name']}</b> — {gift['price']:,}₽\n"
        if gift['description']:
            text += f"   📝 {gift['description']}\n"
        text += "\n"
    
    text += "👇 Нажми на подарок, чтобы оплатить:"
    
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_gifts_keyboard(gifts)
    )

# ============ ОБРАБОТКА ВЫБОРА ПОДАРКА ============

@router.callback_query(lambda c: c.data and c.data.startswith("gift_"))
async def gift_selected(callback: types.CallbackQuery):
    """Обработка выбора подарка"""
    gift_id = int(callback.data.split("_")[1])
    gift = await get_gift_by_id(gift_id)
    
    if not gift:
        await callback.answer("Подарок не найден!", show_alert=True)
        return
    
    # Создаём заказ
    order_id = await create_order(
        user_id=callback.from_user.id,
        gift_id=gift_id,
        amount=gift['price'],
        username=callback.from_user.username
    )
    
    # Текст для оплаты
    payment_text = (
        f"🎁 <b>{gift['icon']} {gift['name']}</b>\n"
        f"💰 Сумма: <b>{gift['price']:,}₽</b>\n\n"
        f"💳 <b>Реквизиты для оплаты:</b>\n"
        f"Банк: {OZON_BANK_NAME}\n"
        f"Карта: ****{OZON_CARD_LAST}\n"
        f"Получатель: {OZON_RECEIVER}\n\n"
        f"📲 <b>Как оплатить:</b>\n"
        f"1. Переведи сумму по номеру карты\n"
        f"2. Нажми «Я оплатил(а)»\n"
        f"3. Отправь скриншот чека\n\n"
        f"🆔 Номер заказа: #{order_id}\n\n"
        f"✅ После проверки чека я подтвержу подарок!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Я оплатил(а)", callback_data=f"paid_{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад к подаркам", callback_data="back_to_gifts")]
    ])
    
    await callback.message.delete()
    await callback.message.answer(
        payment_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()

# ============ ОБРАБОТКА ОПЛАТЫ ============

@router.callback_query(lambda c: c.data and c.data.startswith("paid_"))
async def payment_paid(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь нажал «Я оплатил»"""
    order_id = int(callback.data.split("_")[1])
    
    # Сохраняем order_id в состояние
    await state.update_data(order_id=order_id)
    await state.set_state("waiting_for_receipt")
    
    await callback.message.edit_text(
        f"📸 <b>Отправь скриншот чека</b>\n\n"
        f"Заказ #{order_id}\n\n"
        f"Отправь фото чека одним сообщением.\n"
        f"После проверки я подтвержу подарок.\n\n"
        f"❌ Отмена - /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

# ============ ПОЛУЧЕНИЕ ЧЕКА ============

@router.message(lambda message: message.photo, StateFilter("waiting_for_receipt"))
async def receive_receipt(message: types.Message, state: FSMContext):
    """Получение скриншота чека"""
    data = await state.get_data()
    order_id = data.get('order_id')
    
    photo = message.photo[-1]
    
    # Отправляем админу на подтверждение
    from config import SUPPORT_ADMIN_ID
    
    admin_text = (
        f"🧾 <b>Новый чек на проверку!</b>\n\n"
        f"🆔 Заказ: #{order_id}\n"
        f"👤 Пользователь: @{message.from_user.username or message.from_user.first_name}\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"✅ /approve {order_id} - подтвердить\n"
        f"❌ /reject {order_id} - отклонить"
    )
    
    await message.bot.send_photo(
        SUPPORT_ADMIN_ID,
        photo=photo.file_id,
        caption=admin_text,
        parse_mode="HTML"
    )
    
    await message.answer(
        "✅ <b>Чек отправлен на проверку!</b>\n\n"
        "Я проверю и подтвержу подарок в ближайшее время.\n"
        "Спасибо за поддержку! 💎",
        parse_mode="HTML"
    )
    
    await state.clear()

@router.message(StateFilter("waiting_for_receipt"))
async def invalid_receipt(message: types.Message):
    """Если прислали не фото"""
    await message.answer(
        "❌ Пожалуйста, отправь <b>фото чека</b>.\n\n"
        "Сделай скриншот перевода и отправь сюда.",
        parse_mode="HTML"
    )

# ============ ВОЗВРАТ В КАТАЛОГ ============

@router.callback_query(lambda c: c.data == "back_to_gifts")
async def back_to_gifts(callback: types.CallbackQuery):
    """Возврат в каталог подарков"""
    await show_gifts_catalog(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    from handlers.start import show_main_menu
    await show_main_menu(callback.message)
    await callback.answer()
