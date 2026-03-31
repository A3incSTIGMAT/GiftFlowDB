import logging
from aiogram import Router, types, F
from database import get_gift_by_id, get_all_gifts
from keyboards import get_gift_detail_keyboard, get_gifts_keyboard
from .ozon_payments import send_payment_message

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "show_gifts")
async def show_gifts(callback: types.CallbackQuery):
    gifts = await get_all_gifts()
    if not gifts:
        await callback.message.edit_text("🎁 Подарки временно недоступны.", parse_mode="HTML")
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🎁 <b>Выбери подарок для Ланы:</b>\n\n"
        "💳 <b>Способы оплаты:</b>\n"
        "• СБП (QR-код)\n"
        "• Перевод по реквизитам",
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
        f"💳 Нажми кнопку для оплаты:",
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
    
    await send_payment_message(
        callback.message,
        gift['id'],
        gift['name'],
        gift['price']
    )
    await callback.answer()
