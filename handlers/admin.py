import logging
from aiogram import Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from database import (
    get_pending_orders, confirm_order, reject_order, get_order,
    add_gallery_photo, get_gallery_photos, delete_gallery_photo,
    add_gift, get_all_gifts, update_gift, delete_gift,
    get_statistics, get_top_heroes,
    set_goal, get_goal_progress
)
from keyboards import get_admin_keyboard, get_main_keyboard, get_cancel_keyboard, get_confirm_post_keyboard, get_back_to_admin_keyboard
from config import SUPER_ADMIN_IDS, is_admin, CHANNEL_ID

logger = logging.getLogger(__name__)
router = Router()

# ============ КЛАВИАТУРА ДЛЯ ПОСТА В КАНАЛЕ ============

def get_channel_post_keyboard():
    """Клавиатура для поста в канале (только ссылки - ТОЛЬКО ТАК РАБОТАЕТ В КАНАЛЕ)"""
    bot_username = "GiftFlowDB_bot"
    twitch_url = "https://www.twitch.tv/lanatwitchh"
    instagram_url = "https://www.instagram.com/lanawolfyy"
    telegram_channel_url = "https://t.me/lanatwitchh"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Twitch", url=twitch_url)],
        [InlineKeyboardButton(text="📷 Instagram", url=instagram_url)],
        [InlineKeyboardButton(text="🎁 Подарки", url=f"https://t.me/{bot_username}?start=gifts")],
        [InlineKeyboardButton(text="❓ Помощь", url=f"https://t.me/{bot_username}?start=help")]
    ])
    return keyboard

# ============ АДМИН-ПАНЕЛЬ ============

@router.message(lambda message: message.text == "👑 Админ-панель")
async def admin_panel(message: types.Message, state: FSMContext):
    """Вход в админ-панель"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    
    await state.clear()
    await message.answer(
        "👑 <b>Панель администратора</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

# ============ УПРАВЛЕНИЕ ЗАКАЗАМИ ============

@router.message(lambda message: message.text == "📦 Управление заказами")
async def manage_orders(message: types.Message):
    """Показать список ожидающих заказов"""
    if not is_admin(message.from_user.id):
        return
    
    orders = get_pending_orders()
    
    if not orders:
        await message.answer("📭 Нет ожидающих заказов.")
        return
    
    for order in orders:
        text = (
            f"🆔 <b>Заказ #{order['id']}</b>\n"
            f"🎁 Подарок: {order['gift_name']}\n"
            f"💰 Сумма: {order['amount']}₽\n"
            f"👤 Пользователь: @{order.get('username', 'нет username')}\n"
            f"🆔 ID: {order['user_id']}\n"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{order['id']}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order['id']}")
            ]
        ])
        
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

# ============ ПОДТВЕРЖДЕНИЕ/ОТКЛОНЕНИЕ (CALLBACK) ============

@router.callback_query(lambda c: c.data and c.data.startswith("approve_"))
async def approve_order_callback(callback: types.CallbackQuery):
    """Подтверждение заказа по кнопке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[1])
    success = confirm_order(order_id)
    
    if success:
        order = get_order(order_id)
        if order:
            user_id = order['user_id']
            gift_name = order['gift_name']
            amount = order['amount']
            
            # ========== БЛАГОДАРНОСТЬ ОТ ПЕРВОГО ЛИЦА (ЛАНА) ==========
            thanks_message = (
                f"✨ <b>СПАСИБО ТЕБЕ ЗА ПОДАРОК!</b> ✨\n\n"
                f"🎁 <b>{gift_name}</b>\n"
                f"💰 Сумма: <b>{amount:,}₽</b>\n\n"
                f"❤️ <b>Я очень тронута!</b> Твоя поддержка очень важна для меня.\n\n"
                f"🏆 Ты уже в <b>Топе героев</b>!\n"
                f"📊 Посмотреть топ можно в главном меню.\n\n"
                f"💫 <i>Спасибо, что ты со мной! Твоя забота даёт мне силы и вдохновение.</i>\n\n"
                f"🔗 Подписывайся на мой канал: @lanatwitchh\n\n"
                f"С любовью, <b>Лана</b> ❤️"
            )
            
            await callback.bot.send_message(
                user_id,
                thanks_message,
                parse_mode="HTML"
            )
            
            # Обновляем сообщение в админке
            await callback.message.edit_caption(
                caption=f"✅ ЗАКАЗ #{order_id} ПОДТВЕРЖДЁН\nПользователь уведомлён.\nСумма: {amount}₽\nПодарок: {gift_name}",
                reply_markup=None
            )
            await callback.answer("Подтверждено! Пользователю отправлена благодарность.")
            
            # ========== ПРОВЕРКА ПРОГРЕССА ЦЕЛИ ==========
            progress = get_goal_progress()
            
            # Если цель достигнута (собрано >= цели)
            if progress['collected'] >= progress['target']:
                await callback.bot.send_message(
                    CHANNEL_ID,
                    f"🎉 <b>ЦЕЛЬ ДОСТИГНУТА!</b> 🎉\n\n"
                    f"🎯 {progress['name']}\n"
                    f"💰 Собрано: {progress['collected']:,}₽\n"
                    f"🎯 Цель: {progress['target']:,}₽\n\n"
                    f"❤️ Спасибо всем, кто поддерживал!\n"
                    f"💫 Скоро новая цель!",
                    parse_mode="HTML"
                )
            
        else:
            await callback.answer("Заказ не найден", show_alert=True)
    else:
        await callback.answer("Ошибка подтверждения", show_alert=True)

@router.callback_query(lambda c: c.data and c.data.startswith("reject_"))
async def reject_order_callback(callback: types.CallbackQuery):
    """Отклонение заказа по кнопке"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[1])
    success = reject_order(order_id)
    
    if success:
        order = get_order(order_id)
        if order:
            user_id = order['user_id']
            gift_name = order['gift_name']
            
            reject_message = (
                f"❌ <b>Подарок не подтверждён</b>\n\n"
                f"🎁 {gift_name}\n\n"
                f"⚠️ <b>Причина:</b> чек не прошёл проверку.\n\n"
                f"📸 Пожалуйста, отправьте <b>чёткий скриншот</b> перевода из банка.\n"
                f"Скриншот должен содержать:\n"
                f"• Сумму перевода\n"
                f"• Дату и время\n"
                f"• Номер заказа или комментарий\n\n"
                f"❓ Вопросы: @lanatwitchh\n\n"
                f"🔄 Ты можешь снова выбрать подарок и отправить новый чек.\n\n"
                f"С любовью, <b>Лана</b> ❤️"
            )
            
            await callback.bot.send_message(
                user_id,
                reject_message,
                parse_mode="HTML"
            )
            
            await callback.message.edit_caption(
                caption=f"❌ ЗАКАЗ #{order_id} ОТКЛОНЁН\nПользователь уведомлён.",
                reply_markup=None
            )
            await callback.answer("Отклонено! Пользователь уведомлён.")
        else:
            await callback.answer("Заказ не найден", show_alert=True)
    else:
        await callback.answer("Ошибка отклонения", show_alert=True)

# ============ СТАТИСТИКА ============

@router.message(lambda message: message.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    """Показать статистику"""
    if not is_admin(message.from_user.id):
        return
    
    stats = get_statistics()
    heroes = get_top_heroes(limit=3)
    
    top_text = ""
    for i, hero in enumerate(heroes, 1):
        top_text += f"{i}. @{hero.get('username', 'anon')} — {hero['total_amount']}₽\n"
    
    text = (
        f"📊 <b>СТАТИСТИКА</b>\n\n"
        f"💰 Всего собрано: {stats['total_amount']:,}₽\n"
        f"🎁 Всего подарков: {stats['total_orders']}\n"
        f"👥 Участников: {stats['total_users']}\n"
        f"⏳ Ожидает проверки: {stats['total_pending']}\n\n"
        f"🏆 <b>Топ-3 героев:</b>\n{top_text}"
    )
    
    await message.answer(text, parse_mode="HTML")

# ============ СОЗДАНИЕ ПОСТА (FSM) ============

class PostStates(StatesGroup):
    waiting_for_post_text = State()
    waiting_for_post_photo = State()
    waiting_for_post_confirmation = State()

@router.message(lambda message: message.text == "✏️ Создать пост")
async def create_post(message: types.Message, state: FSMContext):
    """Начало создания поста"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для админа.")
        return
    
    await state.set_state(PostStates.waiting_for_post_text)
    await message.answer(
        "📝 <b>Создание поста</b>\n\n"
        "Отправьте <b>текст</b> для публикации.\n"
        "Можно использовать HTML-разметку.\n\n"
        "❌ Отмена - /cancel",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@router.message(PostStates.waiting_for_post_text)
async def get_post_text(message: types.Message, state: FSMContext):
    """Получение текста поста"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание поста отменено.", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(post_text=message.text)
    await state.set_state(PostStates.waiting_for_post_photo)
    
    await message.answer(
        "📸 <b>Отправьте фото для поста</b>\n\n"
        "Отправьте одно фото или нажмите «Пропустить».\n\n"
        "➡️ <b>Пропустить</b> - опубликовать без фото",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить фото", callback_data="skip_photo")]
        ])
    )

@router.callback_query(lambda c: c.data == "skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    """Пропуск фото"""
    await state.update_data(post_photo=None)
    await state.set_state(PostStates.waiting_for_post_confirmation)
    
    data = await state.get_data()
    post_text = data.get('post_text', '')
    
    await callback.message.delete()
    
    await callback.message.answer(
        f"📢 <b>Предпросмотр поста</b>\n\n{post_text}\n\n"
        f"⚠️ <b>Внимание:</b> Пост будет отправлен в канал с кнопками.",
        parse_mode="HTML",
        reply_markup=get_confirm_post_keyboard()
    )
    await callback.answer()

@router.message(PostStates.waiting_for_post_photo, lambda message: message.photo)
async def get_post_photo(message: types.Message, state: FSMContext):
    """Получение фото для поста"""
    photo = message.photo[-1]
    await state.update_data(post_photo=photo.file_id)
    await state.set_state(PostStates.waiting_for_post_confirmation)
    
    data = await state.get_data()
    post_text = data.get('post_text', '')
    post_photo = data.get('post_photo')
    
    if post_photo:
        await message.answer_photo(
            post_photo,
            caption=f"📢 <b>Предпросмотр поста</b>\n\n{post_text}\n\n⚠️ <b>Внимание:</b> Пост будет отправлен в канал с кнопками.",
            parse_mode="HTML",
            reply_markup=get_confirm_post_keyboard()
        )
    else:
        await message.answer(
            f"📢 <b>Предпросмотр поста</b>\n\n{post_text}\n\n⚠️ <b>Внимание:</b> Пост будет отправлен в канал с кнопками.",
            parse_mode="HTML",
            reply_markup=get_confirm_post_keyboard()
        )

@router.message(PostStates.waiting_for_post_photo)
async def invalid_post_photo(message: types.Message):
    """Если прислали не фото"""
    await message.answer(
        "❌ Пожалуйста, отправьте <b>фото</b> или нажмите «Пропустить».",
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "confirm_post")
async def confirm_post(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение публикации поста с кнопками"""
    data = await state.get_data()
    post_text = data.get('post_text', '')
    post_photo = data.get('post_photo')
    
    channel_keyboard = get_channel_post_keyboard()
    
    try:
        if post_photo:
            await callback.bot.send_photo(
                CHANNEL_ID,
                post_photo,
                caption=post_text,
                parse_mode="HTML",
                reply_markup=channel_keyboard
            )
        else:
            await callback.bot.send_message(
                CHANNEL_ID,
                post_text,
                parse_mode="HTML",
                reply_markup=channel_keyboard
            )
        
        await callback.message.answer(
            "✅ <b>Пост успешно опубликован в канале с кнопками!</b>\n\n"
            "Кнопки: Twitch, Instagram, Подарки, Помощь",
            parse_mode="HTML"
        )
        
        try:
            await callback.message.delete()
        except:
            pass
        
        await callback.answer("✅ Пост опубликован с кнопками!")
        
    except Exception as e:
        logger.error(f"Ошибка публикации поста: {e}")
        await callback.message.answer(
            f"❌ <b>Ошибка публикации:</b>\n<code>{e}</code>",
            parse_mode="HTML"
        )
        await callback.answer()
    
    await state.clear()
    
    await callback.bot.send_message(
        callback.from_user.id,
        "🛠️ <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(lambda c: c.data == "edit_post_text")
async def edit_post_text(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование текста поста"""
    await state.set_state(PostStates.waiting_for_post_text)
    await callback.message.delete()
    await callback.message.answer(
        "📝 <b>Отправьте НОВЫЙ текст для поста</b>\n\n"
        "❌ Отмена - /cancel",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "edit_post_photo")
async def edit_post_photo(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование фото поста"""
    await state.set_state(PostStates.waiting_for_post_photo)
    await callback.message.delete()
    await callback.message.answer(
        "📸 <b>Отправьте НОВОЕ фото для поста</b>\n\n"
        "Отправьте одно фото или нажмите «Пропустить».",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить фото", callback_data="skip_photo")]
        ])
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "cancel_post")
async def cancel_post(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания поста"""
    await state.clear()
    await callback.message.edit_text("❌ Создание поста отменено.")
    await callback.bot.send_message(
        callback.from_user.id,
        "🛠️ <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

# ============ УПРАВЛЕНИЕ ГАЛЕРЕЕЙ ============

class GalleryStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_description = State()

@router.message(lambda message: message.text == "🖼️ Управление галереей")
async def manage_gallery(message: types.Message):
    """Управление галереей"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return
    
    images = get_gallery_photos(limit=20)
    
    if not images:
        await message.answer(
            "🖼️ <b>Галерея пуста</b>\n\n"
            "Добавьте фото кнопкой ниже.",
            parse_mode="HTML"
        )
    else:
        text = "🖼️ <b>Галерея</b>\n\n"
        for img in images[:10]:
            text += f"📷 ID: {img['id']} | {img['description'][:30] if img['description'] else 'Без описания'}\n"
        await message.answer(text, parse_mode="HTML")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить фото", callback_data="add_gallery_photo")],
        [InlineKeyboardButton(text="❌ Удалить фото", callback_data="delete_gallery_photo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer("Выберите действие:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "add_gallery_photo")
async def add_gallery_photo_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Запрос на добавление фото в галерею"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!", show_alert=True)
        return
    
    await state.set_state(GalleryStates.waiting_for_photo)
    await callback.message.edit_text(
        "📸 <b>Добавление фото в галерею</b>\n\n"
        "Отправьте фото.\n"
        "После отправки можно добавить описание.\n\n"
        "❌ Отмена - /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(GalleryStates.waiting_for_photo, lambda message: message.photo)
async def save_gallery_photo(message: types.Message, state: FSMContext):
    """Сохранение фото в галерею"""
    photo = message.photo[-1]
    await state.update_data(photo_id=photo.file_id)
    await state.set_state(GalleryStates.waiting_for_description)
    await message.answer(
        "📝 <b>Добавьте описание к фото</b>\n\n"
        "Отправьте текст или нажмите «Пропустить» - /skip",
        parse_mode="HTML"
    )

@router.message(GalleryStates.waiting_for_photo)
async def invalid_gallery_photo(message: types.Message):
    """Если прислали не фото"""
    await message.answer("❌ Пожалуйста, отправьте фото.")

@router.message(GalleryStates.waiting_for_description, lambda message: message.text == "/skip")
async def skip_gallery_description(message: types.Message, state: FSMContext):
    """Пропуск описания"""
    data = await state.get_data()
    photo_id = data.get('photo_id')
    
    success = add_gallery_photo(photo_id, "")
    
    await state.clear()
    if success:
        await message.answer("✅ <b>Фото добавлено в галерею!</b>", reply_markup=get_admin_keyboard())
    else:
        await message.answer("❌ Ошибка при добавлении фото.", reply_markup=get_admin_keyboard())

@router.message(GalleryStates.waiting_for_description)
async def save_gallery_description(message: types.Message, state: FSMContext):
    """Сохранение описания"""
    data = await state.get_data()
    photo_id = data.get('photo_id')
    
    success = add_gallery_photo(photo_id, message.text)
    
    await state.clear()
    if success:
        await message.answer(
            f"✅ <b>Фото добавлено в галерею!</b>\n\nОписание: {message.text}",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer("❌ Ошибка при добавлении фото.", reply_markup=get_admin_keyboard())

@router.callback_query(lambda c: c.data == "delete_gallery_photo")
async def delete_gallery_photo_prompt(callback: types.CallbackQuery):
    """Запрос ID фото для удаления"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "❌ <b>Удаление фото из галереи</b>\n\n"
        "Отправьте ID фото для удаления.\n\n"
        "ID можно посмотреть в списке галереи.\n\n"
        "❌ Отмена - /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(lambda message: message.text and message.text.isdigit())
async def delete_gallery_photo_by_id(message: types.Message):
    """Удаление фото по ID"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return
    
    photo_id = int(message.text)
    success = delete_gallery_photo(photo_id)
    
    if success:
        await message.answer(f"✅ Фото #{photo_id} удалено из галереи.", reply_markup=get_admin_keyboard())
    else:
        await message.answer(f"❌ Фото #{photo_id} не найдено.", reply_markup=get_admin_keyboard())

# ============ ДОБАВЛЕНИЕ ПОДАРКА ============

class GiftStates(StatesGroup):
    waiting_for_gift_name = State()
    waiting_for_gift_price = State()
    waiting_for_gift_description = State()
    waiting_for_gift_icon = State()

@router.message(lambda message: message.text == "➕ Добавить подарок")
async def add_gift_start(message: types.Message, state: FSMContext):
    """Начало добавления подарка"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для админа.")
        return
    
    await state.set_state(GiftStates.waiting_for_gift_name)
    await message.answer(
        "🎁 <b>Добавление подарка</b>\n\n"
        "Введите <b>название</b> подарка:\n"
        "Пример: Конфетка\n\n"
        "❌ Отмена - /cancel",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@router.message(GiftStates.waiting_for_gift_name)
async def get_gift_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(gift_name=message.text)
    await state.set_state(GiftStates.waiting_for_gift_price)
    await message.answer(
        "💰 Введите <b>цену</b> подарка (число):\n"
        "Пример: 100\n\n"
        "❌ Отмена - /cancel",
        parse_mode="HTML"
    )

@router.message(GiftStates.waiting_for_gift_price)
async def get_gift_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_admin_keyboard())
        return
    
    try:
        price = int(message.text)
        await state.update_data(gift_price=price)
        await state.set_state(GiftStates.waiting_for_gift_description)
        await message.answer(
            "📝 Введите <b>описание</b> подарка:\n"
            "Пример: Маленькая сладость для Ланы\n\n"
            "Или нажмите «Пропустить» - /skip",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Цена должна быть числом. Попробуйте еще раз:")

@router.message(GiftStates.waiting_for_gift_description, lambda message: message.text == "/skip")
async def skip_gift_description(message: types.Message, state: FSMContext):
    await state.update_data(gift_description="")
    await state.set_state(GiftStates.waiting_for_gift_icon)
    await message.answer(
        "🎨 Введите <b>иконку</b> для подарка (один emoji):\n"
        "Пример: 🎁 🍬 ☕\n\n"
        "Или нажмите «Пропустить» - /skip",
        parse_mode="HTML"
    )

@router.message(GiftStates.waiting_for_gift_description)
async def get_gift_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(gift_description=message.text)
    await state.set_state(GiftStates.waiting_for_gift_icon)
    await message.answer(
        "🎨 Введите <b>иконку</b> для подарка (один emoji):\n"
        "Пример: 🎁 🍬 ☕\n\n"
        "Или нажмите «Пропустить» - /skip",
        parse_mode="HTML"
    )

@router.message(GiftStates.waiting_for_gift_icon, lambda message: message.text == "/skip")
async def skip_gift_icon(message: types.Message, state: FSMContext):
    await state.update_data(gift_icon="🎁")
    data = await state.get_data()
    
    success = add_gift(
        name=data['gift_name'],
        price=data['gift_price'],
        description=data.get('gift_description', ''),
        icon=data.get('gift_icon', '🎁')
    )
    
    await state.clear()
    if success:
        await message.answer(
            f"✅ <b>Подарок добавлен!</b>\n\n"
            f"🎁 {data['gift_name']}\n"
            f"💰 {data['gift_price']}₽\n"
            f"📝 {data.get('gift_description', 'Без описания')}",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer("❌ Ошибка при добавлении подарка.", reply_markup=get_admin_keyboard())

@router.message(GiftStates.waiting_for_gift_icon)
async def get_gift_icon(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_admin_keyboard())
        return
    
    icon = message.text.strip()
    if len(icon) > 2:
        icon = "🎁"
    
    await state.update_data(gift_icon=icon)
    data = await state.get_data()
    
    success = add_gift(
        name=data['gift_name'],
        price=data['gift_price'],
        description=data.get('gift_description', ''),
        icon=data.get('gift_icon', '🎁')
    )
    
    await state.clear()
    if success:
        await message.answer(
            f"✅ <b>Подарок добавлен!</b>\n\n"
            f"{icon} {data['gift_name']}\n"
            f"💰 {data['gift_price']}₽\n"
            f"📝 {data.get('gift_description', 'Без описания')}",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
    else:
        await message.answer("❌ Ошибка при добавлении подарка.", reply_markup=get_admin_keyboard())

# ============ ТОП ГЕРОЕВ (АДМИН) ============

@router.message(lambda message: message.text == "🏆 Топ героев (админ)")
async def admin_top_heroes(message: types.Message):
    """Просмотр топа героев для админа"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return
    
    heroes = get_top_heroes(limit=20)
    
    if not heroes:
        await message.answer("🏆 Топ героев пока пуст.")
        return
    
    text = "🏆 <b>Топ героев (админ-панель)</b>\n\n"
    for i, hero in enumerate(heroes[:10], 1):
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        medal = medals.get(i, f"{i}.")
        username = hero.get('username') or f"user_{hero['user_id']}"
        text += f"{medal} @{username} — {hero['total_amount']:,}₽\n"
    
    await message.answer(text, parse_mode="HTML")

# ============ КОМАНДА ДЛЯ УСТАНОВКИ ЦЕЛИ ============

@router.message(Command("goal"))
async def set_goal_command(message: types.Message):
    """Установить цель: /goal Название_цели Сумма"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await message.answer(
            "❌ <b>Использование:</b>\n"
            "/goal Название_цели Сумма\n\n"
            "<b>Примеры:</b>\n"
            "/goal Роллы 3000\n"
            "/goal Новый микрофон 15000\n"
            "/goal Компьютер 150000",
            parse_mode="HTML"
        )
        return
    
    # Собираем название (всё до последнего слова)
    goal_name = " ".join(args[1:-1])
    try:
        goal_amount = int(args[-1])
    except ValueError:
        await message.answer("❌ Сумма должна быть числом!")
        return
    
    if goal_amount <= 0:
        await message.answer("❌ Сумма должна быть больше 0!")
        return
    
    # Сохраняем цель
    set_goal(goal_name, goal_amount)
    
    # Получаем прогресс
    progress = get_goal_progress()
    
    # Формируем пост для канала
    post_text = f"""
🎯 <b>НОВЫЙ СБОР: {progress['name']}</b>
💰 Цель: {progress['target']:,}₽
📊 Собрано: {progress['collected']:,}₽ ({progress['percent']}%)

{progress['bars']} {progress['percent']}%

💫 До цели: {progress['remaining']:,}₽

💳 Поддержать: @GiftFlowDB_bot
"""
    
    # Отправляем в канал
    try:
        await message.bot.send_message(CHANNEL_ID, post_text, parse_mode="HTML")
        await message.answer(
            f"✅ <b>Цель установлена!</b>\n\n"
            f"🎯 {goal_name}\n"
            f"💰 {goal_amount:,}₽\n\n"
            f"📢 Пост отправлен в канал.",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки в канал: {e}")

# ============ ВОЗВРАТ В АДМИНКУ ============

@router.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в админ-панель"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!", show_alert=True)
        return
    
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "🛠️ <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()
