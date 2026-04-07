from aiogram import Router, types
from aiogram.filters import Command
from keyboards import get_gifts_keyboard, get_payment_keyboard, get_main_keyboard
from database import get_all_gifts, get_top_heroes, add_transaction, update_top_heroes
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.message(lambda message: message.text == "🎁 Каталог подарков")
async def show_gifts(message: types.Message):
    """Показать каталог подарков"""
    gifts = await get_all_gifts()
    
    if not gifts:
        await message.answer("📦 Каталог подарков временно пуст. Загляните позже!")
        return
    
    text = "🎁 <b>Наши подарки для Ланы</b>\n\n"
    for gift in gifts:
        text += f"{gift['icon']} <b>{gift['name']}</b> — {gift['price']}₽\n"
        if gift['description']:
            text += f"   └ {gift['description']}\n"
    
    text += "\n👇 <i>Нажми на кнопку ниже, чтобы выбрать подарок</i>"
    
    keyboard = get_gifts_keyboard(gifts)
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.message(lambda message: message.text == "🏆 Топ героев")
async def show_top_heroes(message: types.Message):
    """Показать топ героев (донатеров)"""
    heroes = await get_top_heroes(limit=10)
    
    if not heroes:
        await message.answer(
            "🏆 <b>Топ героев пока пуст</b>\n\n"
            "💝 <i>Будь первым — подари подарок Лане и попади в топ!</i>\n\n"
            "Нажми «🎁 Каталог подарков», чтобы выбрать подарок.",
            parse_mode="HTML"
        )
        return
    
    text = "🏆 <b>Топ героев канала</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, hero in enumerate(heroes[:10]):
        if i < 3:
            medal = medals[i]
        else:
            medal = "🎖️"
        
        username = hero.get('username') or f"user_{hero['user_id']}"
        # Обрезаем длинные имена
        if len(username) > 20:
            username = username[:17] + "..."
        
        text += f"{medal} <b>{username}</b> — {hero['total_amount']:,}₽\n"
    
    text += "\n💡 <i>Топ обновляется автоматически после каждого доната!</i>\n"
    text += "🎁 <i>В конце месяца — секретный приз для лидеров!</i>"
    
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text == "🎁 О конкурсе")
async def show_contest(message: types.Message):
    """Показать информацию о конкурсе"""
    text = (
        "🎉 <b>КОНКУРС ДОНАТЕРОВ</b> 🎉\n\n"
        "До 7 мая 2026 года собираем топ донатеров канала!\n\n"
        "🏆 <b>Что получит победитель?</b>\n"
        "🤫 <i>Секретный приз от Ланы!</i> (спойлер: это очень круто)\n\n"
        "📊 <b>Как участвовать?</b>\n"
        "1. Заходи в «🎁 Каталог подарков»\n"
        "2. Выбирай любой подарок\n"
        "3. Оплачивай через СБП или карту\n"
        "4. Попадай в топ героев!\n\n"
        "⏰ <b>Дедлайн:</b> 7 мая 2026\n\n"
        "🔥 <i>Чем больше сумма донатов — тем выше шанс на победу!</i>\n\n"
        "📢 <b>Победитель будет объявлен в канале @lanatwitchh</b>"
    )
    
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text == "📺 Twitch")
async def twitch_link(message: types.Message):
    """Ссылка на Twitch"""
    await message.answer(
        "🎮 <b>Twitch канал Ланы</b>\n\n"
        "Подписывайся и не пропускай стримы:\n"
        "👉 <a href='https://twitch.tv/lana'>twitch.tv/lana</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(lambda message: message.text == "📷 Instagram")
async def instagram_link(message: types.Message):
    """Ссылка на Instagram"""
    await message.answer(
        "📸 <b>Instagram Ланы</b>\n\n"
        "Подписывайся на фото и сторис:\n"
        "👉 <a href='https://instagram.com/lana'>instagram.com/lana</a>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(lambda message: message.text == "🆘 Помощь")
async def help_message(message: types.Message):
    """Помощь"""
    text = (
        "🆘 <b>Помощь по боту</b>\n\n"
        "📌 <b>Как подарить подарок?</b>\n"
        "1. Нажми «🎁 Каталог подарков»\n"
        "2. Выбери понравившийся подарок\n"
        "3. Оплати через СБП или карту\n"
        "4. После подтверждения оплаты ты попадёшь в топ героев!\n\n"
        "🏆 <b>Топ героев</b>\n"
        "Обновляется автоматически. Топ-3 получают особое упоминание в еженедельном посте.\n\n"
        "🎁 <b>Конкурс</b>\n"
        "До 7 мая — секретный приз для лучших донатеров месяца.\n\n"
        "❓ <b>Вопросы и проблемы</b>\n"
        "По всем вопросам пиши менеджеру: @lanatwitchh\n\n"
        "💝 <i>Спасибо, что поддерживаешь Лану!</i>"
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(lambda c: c.data.startswith("gift_"))
async def select_gift(callback: types.CallbackQuery):
    """Выбор подарка"""
    gift_id = int(callback.data.split("_")[1])
    
    gifts = await get_all_gifts()
    gift = next((g for g in gifts if g['id'] == gift_id), None)
    
    if not gift:
        await callback.answer("Подарок не найден!", show_alert=True)
        return
    
    text = (
        f"{gift['icon']} <b>{gift['name']}</b>\n\n"
        f"💰 Цена: <b>{gift['price']}₽</b>\n"
        f"📝 Описание: {gift['description'] or 'Нет описания'}\n\n"
        f"👇 <i>Выбери способ оплаты:</i>"
    )
    
    keyboard = get_payment_keyboard(gift_id, gift['name'], gift['price'])
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_gifts")
async def back_to_gifts(callback: types.CallbackQuery):
    """Назад к каталогу подарков"""
    gifts = await get_all_gifts()
    keyboard = get_gifts_keyboard(gifts)
    
    text = "🎁 <b>Выбери подарок для Ланы:</b>\n\n👇 <i>Нажми на кнопку ниже</i>"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main_from_gifts(callback: types.CallbackQuery):
    """Назад в главное меню"""
    keyboard = get_main_keyboard()
    await callback.message.delete()
    await callback.message.answer(
        "🎁 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()
