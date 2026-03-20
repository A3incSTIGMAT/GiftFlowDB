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
    
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()
