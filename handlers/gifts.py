from aiogram import Router, types, F
from database import get_gift_by_id, add_transaction, get_all_gifts
from keyboards import get_gift_detail_keyboard, get_gifts_keyboard
from donatepay import create_donatepay_invoice
from config import ADMIN_IDS, FEE_PERCENT, PROFIT_SPLIT
import asyncio

router = Router()

@router.callback_query(F.data == "show_gifts")
async def show_gifts(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎁 <b>Выбери подарок для Ланы:</b>\n\n"
        "После оплаты подарок появится на стриме!",
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
    
    await callback.message.edit_text(
        f"🎁 <b>{gift['name']}</b>\n\n"
        f"💰 Цена: {gift['price']}₽\n"
        f"📝 {gift.get('description', 'Поддержи Лану!')}\n\n"
        f"Нажми кнопку для оплаты:",
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
    
    # Создаём счёт в DonatePay
    payment_url = await create_donatepay_invoice(
        amount=gift['price'],
        description=gift['name'],
        user_id=callback.from_user.id
    )
    
    if payment_url:
        # Сохраняем транзакцию
        fee = int(gift['price'] * FEE_PERCENT)
        await add_transaction(
            callback.from_user.id,
            callback.from_user.username,
            gift['name'],
            gift['price'],
            fee
        )
        
        await callback.message.edit_text(
            f"✅ <b>Счёт создан!</b>\n\n"
            f"🎁 Подарок: {gift['name']}\n"
            f"💰 Сумма: {gift['price']}₽\n\n"
            f"🔗 <a href='{payment_url}'>Нажми сюда для оплаты</a>\n\n"
            f"После оплаты подарок автоматически придёт на стрим!",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer("❌ Ошибка создания счета. Попробуй позже.")
    
    await callback.answer()
