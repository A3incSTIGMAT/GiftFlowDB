import logging
from io import BytesIO
from aiogram import Router, types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

import qrcode

from database import get_all_gifts, create_order, get_gift_by_id
from config import OZON_CARD_LAST, OZON_BANK_NAME, OZON_RECEIVER, SUPPORT_ADMIN_ID

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
    
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main_menu")])
    
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
    text += "\n👇 Нажми на подарок, чтобы оплатить:"
    
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
    
    # Формируем данные для QR-кода
    qr_text = (
        f"Оплата подарка для Ланы\n"
        f"Подарок: {gift['name']}\n"
        f"Сумма: {gift['price']}₽\n"
        f"Номер заказа: #{order_id}\n"
        f"Банк: {OZON_BANK_NAME}\n"
        f"Карта: ****{OZON_CARD_LAST}\n"
        f"Получатель: {OZON_RECEIVER}"
    )
    
    # Генерируем QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=8,
        border=3,
    )
    qr.add_data(qr_text)
    qr.make(fit=True)
    
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # Сохраняем в BytesIO
    bio = BytesIO()
    qr_image.save(bio, format='PNG')
    bio.seek(0)
    
    # Удаляем сообщение с каталогом
    await callback.message.delete()
    
    # Текст для оплаты
    payment_text = (
        f"🎁 <b>{gift['icon']} {gift['name']}</b>\n"
        f"💰 Сумма: <b>{gift['price']:,}₽</b>\n\n"
        f"💳 <b>Реквизиты для оплаты:</b>\n"
        f"Банк: {OZON_BANK_NAME}\n"
        f"Карта: ****{OZON_CARD_LAST}\n"
        f"Получатель: {OZON_RECEIVER}\n\n"
        f"🆔 Номер заказа: #{order_id}\n\n"
        f"📱 Отсканируйте QR-код или переведите по реквизитам\n\n"
        f"✅ После оплаты нажмите «Я оплатил(а)» и отправьте чек"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Я оплатил(а)", callback_data=f"paid_{order_id}")],
        [InlineKeyboardButton(text="🔙 Назад к подаркам", callback_data="back_to_gifts_catalog")]
    ])
    
    # Отправляем QR-код и текст
    await callback.message.answer_photo(
        photo=FSInputFile(bio, filename=f"qr_order_{order_id}.png"),
        caption=payment_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()

# ============ ОБРАБОТКА ОПЛАТЫ ============

class PaymentStates(StatesGroup):
    waiting_for_receipt = State()

@router.callback_query(lambda c: c.data and c.data.startswith("paid_"))
async def payment_paid(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь нажал «Я оплатил»"""
    order_id = int(callback.data.split("_")[1])
    
    # Сохраняем order_id в состояние
    await state.update_data(order_id=order_id)
    await state.set_state(PaymentStates.waiting_for_receipt)
    
    # Редактируем сообщение с QR-кодом
    await callback.message.edit_caption(
        caption=(
            f"📸 <b>Отправьте скриншот чека</b>\n\n"
            f"Заказ #{order_id}\n\n"
            f"Отправьте фото чека одним сообщением.\n"
            f"После проверки я подтвержу подарок.\n\n"
            f"❌ Отмена - /cancel"
        ),
        parse_mode="HTML"
    )
    # Убираем кнопки
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()

# ============ ПОЛУЧЕНИЕ ЧЕКА ============

@router.message(PaymentStates.waiting_for_receipt, lambda message: message.photo)
async def receive_receipt(message: types.Message, state: FSMContext):
    """Получение скриншота чека"""
    data = await state.get_data()
    order_id = data.get('order_id')
    
    if not order_id:
        await message.answer(
            "❌ Ошибка: заказ не найден.\nПожалуйста, начните оплату заново.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    photo = message.photo[-1]
    
    admin_text = (
        f"🧾 <b>Новый чек на проверку!</b>\n\n"
        f"🆔 Заказ: #{order_id}\n"
        f"👤 Пользователь: @{message.from_user.username or message.from_user.first_name}\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"✅ /approve_{order_id} - подтвердить\n"
        f"❌ /reject_{order_id} - отклонить"
    )
    
    # Отправляем админу
    await message.bot.send_photo(
        SUPPORT_ADMIN_ID,
        photo=photo.file_id,
        caption=admin_text,
        parse_mode="HTML"
    )
    
    # Подтверждение пользователю
    await message.answer(
        "✅ <b>Чек отправлен на проверку!</b>\n\n"
        "Администратор проверит и подтвердит подарок в ближайшее время.\n"
        "Спасибо за поддержку! 💎",
        parse_mode="HTML"
    )
    
    await state.clear()

@router.message(PaymentStates.waiting_for_receipt)
async def invalid_receipt(message: types.Message):
    """Если прислали не фото"""
    await message.answer(
        "❌ Пожалуйста, отправьте <b>фото чека</b>.\n\n"
        "Сделайте скриншот перевода и отправьте сюда.\n\n"
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
    # Создаём фейковое сообщение для start_command
    class FakeMessage:
        def __init__(self, from_user, chat, bot):
            self.from_user = from_user
            self.chat = chat
            self.bot = bot
            self.text = "/start"
    
    fake_msg = FakeMessage(
        from_user=callback.from_user,
        chat=callback.message.chat,
        bot=callback.bot
    )
    await start_command(fake_msg, state)
    await callback.answer()
