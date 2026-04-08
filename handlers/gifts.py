import logging
from io import BytesIO
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

import qrcode

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
    gifts = await get_all_gifts()
    
    if not gifts:
        await message.answer(
            "🎁 <b>Каталог подарков пока пуст</b>\n\nЗагляни позже!",
            parse_mode="HTML"
        )
        return
    
    text = "🎁 <b>Каталог подарков</b>\n\n"
    for gift in gifts:
        text += f"• {gift['icon']} {gift['name']} — {gift['price']:,}₽\n"
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
    try:
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
        qr_text = f"Оплата подарка для Ланы: {gift['name']} {gift['price']}₽ Заказ #{order_id}"
        
        # Генерируем QR-код
        qr = qrcode.QRCode(box_size=8, border=2)
        qr.add_data(qr_text)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Сохраняем в BytesIO и конвертируем в BufferedInputFile
        bio = BytesIO()
        qr_image.save(bio, format='PNG')
        bio.seek(0)
        photo_bytes = bio.getvalue()
        
        # Текст для оплаты
        payment_text = (
            f"🎁 <b>{gift['icon']} {gift['name']}</b>\n"
            f"💰 Сумма: <b>{gift['price']:,}₽</b>\n\n"
            f"💳 <b>Реквизиты для оплаты:</b>\n"
            f"🏦 {OZON_BANK_NAME}\n"
            f"💳 Карта: ****{OZON_CARD_LAST}\n"
            f"👤 Получатель: {OZON_RECEIVER}\n\n"
            f"🆔 <b>Номер заказа: #{order_id}</b>\n\n"
            f"📱 <b>Отсканируйте QR-код:</b>\n\n"
            f"📲 <b>Как оплатить:</b>\n"
            f"1. Отсканируйте QR-код или переведите по реквизитам\n"
            f"2. Нажмите «Я оплатил(а)»\n"
            f"3. Отправьте скриншот чека\n\n"
            f"✅ После проверки чека я подтвержу подарок!"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data=f"paid_{order_id}")],
            [InlineKeyboardButton(text="🔙 Назад к подаркам", callback_data="back_to_gifts_catalog")]
        ])
        
        # Удаляем старое сообщение
        await callback.message.delete()
        
        # Отправляем фото с QR-кодом используя BufferedInputFile
        photo_file = BufferedInputFile(photo_bytes, filename=f"qr_{order_id}.png")
        await callback.message.answer_photo(
            photo=photo_file,
            caption=payment_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка gift_selected: {e}")
        await callback.answer("Ошибка, попробуйте позже", show_alert=True)

# ============ ОБРАБОТКА ОПЛАТЫ ============

@router.callback_query(lambda c: c.data and c.data.startswith("paid_"))
async def payment_paid(callback: types.CallbackQuery, state: FSMContext):
    """Пользователь нажал «Я оплатил»"""
    try:
        order_id = int(callback.data.split("_")[1])
        
        await state.update_data(order_id=order_id)
        await state.set_state(PaymentStates.waiting_for_receipt)
        
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
        await message.answer("❌ Ошибка: заказ не найден. Начните оплату заново.", parse_mode="HTML")
        await state.clear()
        return
    
    photo = message.photo[-1]
    
    admin_text = (
        f"🧾 <b>НОВЫЙ ЧЕК!</b>\n\n"
        f"🆔 Заказ: #{order_id}\n"
        f"👤 Пользователь: @{message.from_user.username or message.from_user.first_name}\n"
        f"🆔 ID: {message.from_user.id}\n\n"
        f"✅ /approve_{order_id} - ПОДТВЕРДИТЬ\n"
        f"❌ /reject_{order_id} - ОТКЛОНИТЬ"
    )
    
    await message.bot.send_photo(SUPPORT_ADMIN_ID, photo=photo.file_id, caption=admin_text, parse_mode="HTML")
    
    await message.answer(
        "✅ <b>Чек отправлен на проверку!</b>\n\nСпасибо за поддержку! 💎",
        parse_mode="HTML"
    )
    await state.clear()

@router.message(PaymentStates.waiting_for_receipt)
async def invalid_receipt(message: types.Message):
    """Если прислали не фото"""
    await message.answer(
        "❌ Пожалуйста, отправьте <b>ФОТО чека</b>.\n\n❌ Отмена - /cancel",
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
