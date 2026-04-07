import logging
from aiogram import Router, types, F
from database import get_gift_by_id, add_transaction, get_all_gifts, get_top_heroes, get_monthly_stats
from keyboards import get_gift_detail_keyboard, get_gifts_keyboard, get_back_keyboard
from .ozon_payments import send_payment_message

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "show_gifts")
async def show_gifts(callback: types.CallbackQuery):
    gifts = await get_all_gifts()
    if not gifts:
        await callback.message.edit_text(
            "🎁 <b>Каталог подарков</b>\n\nПодарки временно недоступны.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "🎁 <b>Выбери подарок для Ланы:</b>\n\n"
        "💳 <b>Способы оплаты:</b>\n"
        "• СБП (QR-код)\n"
        "• Перевод по реквизитам\n\n"
        "💡 <i>Все платежи — добровольные пожертвования</i>",
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


# ========== ТОП ГЕРОЕВ ==========
@router.callback_query(F.data == "show_top_heroes")
async def show_top_heroes(callback: types.CallbackQuery):
    """Показать топ донатеров канала с уникальными эмодзи"""
    heroes = await get_top_heroes(limit=10)
    stats = await get_monthly_stats()
    
    if not heroes:
        await callback.message.edit_text(
            "🏆 <b>Топ героев канала</b>\n\n"
            "Пока никого нет. Будь первым! 🎁\n\n"
            "💡 <i>Дари подарки и попади в топ!</i>",
            parse_mode="HTML",
            reply_markup=await get_back_keyboard()
        )
        await callback.answer()
        return
    
    text = "🏆 <b>Топ героев канала</b>\n\n"
    text += f"📊 За месяц собрано: {stats['total_monthly']}₽\n"
    text += f"👥 Уникальных донатеров: {stats['unique_donors']}\n\n"
    text += "🥇 <b>Лидеры месяца:</b>\n\n"
    
    # Специальные эмодзи для топ-3
    special_emojis = {
        0: "👑",  # топ-1
        1: "⭐️",  # топ-2
        2: "🌟"    # топ-3
    }
    
    for i, hero in enumerate(heroes[:3]):
        emoji = special_emojis.get(i, "🥇" if i == 0 else "🥈" if i == 1 else "🥉")
        username = hero.get('username') or f"user_{hero['user_id']}"
        text += f"{emoji} <b>{username}</b> — {hero['total_amount']}₽\n"
    
    if len(heroes) > 3:
        text += "\n<b>Остальные герои:</b>\n"
        for hero in heroes[3:]:
            username = hero.get('username') or f"user_{hero['user_id']}"
            text += f"🎖️ {username} — {hero['total_amount']}₽\n"
    
    text += "\n💡 <i>Топ обновляется каждый месяц. Будь в числе лучших!</i>"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=await get_back_keyboard()
    )
    await callback.answer()
