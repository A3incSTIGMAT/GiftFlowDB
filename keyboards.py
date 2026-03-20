from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import TWITCH_URL, INSTAGRAM_URL, DONATEPAY_URL
from database import get_all_gifts

async def get_main_menu_keyboard():
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📺 Twitch", url=TWITCH_URL),
        InlineKeyboardButton(text="📷 Instagram", url=INSTAGRAM_URL),
        width=2
    )
    
    builder.row(
        InlineKeyboardButton(text="🎁 Каталог подарков", callback_data="show_gifts"),
        width=1
    )
    
    builder.row(
        InlineKeyboardButton(text="💳 DonatePay", url=DONATEPAY_URL),
        InlineKeyboardButton(text="💬 Помощь", callback_data="contact_support"),
        width=2
    )
    
    return builder.as_markup()

async def get_gifts_keyboard():
    gifts = await get_all_gifts()
    builder = InlineKeyboardBuilder()
    
    for gift in gifts:
        builder.button(
            text=f"🎁 {gift['name']} | {gift['price']}₽",
            callback_data=f"gift_{gift['id']}"
        )
    
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"),
        width=1
    )
    
    builder.adjust(1)
    return builder.as_markup()

async def get_gift_detail_keyboard(gift_id: int):
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="💳 Оплатить", callback_data=f"pay_{gift_id}"),
        width=1
    )
    
    builder.row(
        InlineKeyboardButton(text="⬅️ К списку", callback_data="show_gifts"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main"),
        width=2
    )
    
    return builder.as_markup()

async def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="show_gifts")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()

async def get_admin_keyboard(user_id: int):
    from config import SUPER_ADMIN_ID, SUPPORT_ADMIN_ID
    
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="📸 Галерея", callback_data="admin_gallery")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    
    if user_id == SUPER_ADMIN_ID:
        builder.button(text="📊 Статистика", callback_data="admin_stats")
    
    builder.adjust(2)
    return builder.as_markup()
