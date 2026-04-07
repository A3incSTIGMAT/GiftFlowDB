import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import is_admin, is_super_admin, add_gallery_photo, get_gallery_photos, delete_gallery_photo, add_gift, get_all_gifts, update_gift
from keyboards import get_admin_keyboard, get_main_keyboard, get_cancel_keyboard, get_confirm_post_keyboard, get_back_to_admin_keyboard
from config import SUPER_ADMIN_ID

logger = logging.getLogger(__name__)
router = Router()

# ============ СОЗДАНИЕ ПОСТА (FSM) ============

class PostStates(StatesGroup):
    waiting_for_post_text = State()
    waiting_for_post_photo = State()
    waiting_for_post_confirmation = State()

@router.message(lambda message: message.text == "✏️ Создать пост")
async def create_post(message: types.Message, state: FSMContext):
    """Начало создания поста"""
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только для супер-админа.")
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
        f"⚠️ <b>Внимание:</b> Пост будет отправлен в канал.",
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
            caption=f"📢 <b>Предпросмотр поста</b>\n\n{post_text}\n\n⚠️ <b>Внимание:</b> Пост будет отправлен в канал.",
            parse_mode="HTML",
            reply_markup=get_confirm_post_keyboard()
        )
    else:
        await message.answer(
            f"📢 <b>Предпросмотр поста</b>\n\n{post_text}\n\n⚠️ <b>Внимание:</b> Пост будет отправлен в канал.",
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
    """Подтверждение публикации поста"""
    data = await state.get_data()
    post_text = data.get('post_text', '')
    post_photo = data.get('post_photo')
    
    from config import CHANNEL_ID
    
    try:
        if post_photo:
            await callback.bot.send_photo(
                CHANNEL_ID,
                post_photo,
                caption=post_text,
                parse_mode="HTML"
            )
        else:
            await callback.bot.send_message(
                CHANNEL_ID,
                post_text,
                parse_mode="HTML"
            )
        
        await callback.message.edit_text(
            "✅ <b>Пост успешно опубликован в канале!</b>",
            parse_mode="HTML"
        )
        await callback.answer("Пост опубликован!")
        
    except Exception as e:
        logger.error(f"Ошибка публикации поста: {e}")
        await callback.message.edit_text(
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

@router.message(lambda message: message.text == "🖼️ Управление галереей")
async def manage_gallery(message: types.Message):
    """Управление галереей"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return
    
    images = await get_gallery_photos(limit=20)
    
    if not images:
        await message.answer(
            "🖼️ <b>Галерея пуста</b>\n\n"
            "Добавьте фото командой /add_photo",
            parse_mode="HTML"
        )
        return
    
    text = "🖼️ <b>Галерея</b>\n\n"
    for img in images[:10]:
        text += f"📷 ID: {img['id']} | {img['description'][:30] if img['description'] else 'Без описания'}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить фото", callback_data="add_gallery_photo")],
        [InlineKeyboardButton(text="❌ Удалить фото", callback_data="delete_gallery_photo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    
    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

@router.callback_query(lambda c: c.data == "add_gallery_photo")
async def add_gallery_photo_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Запрос на добавление фото в галерею"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!", show_alert=True)
        return
    
    await state.set_state("waiting_for_gallery_photo")
    await callback.message.edit_text(
        "📸 <b>Добавление фото в галерею</b>\n\n"
        "Отправьте фото.\n"
        "После отправки можно добавить описание.\n\n"
        "❌ Отмена - /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(lambda message: message.photo, StateFilter="waiting_for_gallery_photo")
async def save_gallery_photo(message: types.Message, state: FSMContext):
    """Сохранение фото в галерею"""
    photo = message.photo[-1]
    await state.update_data(gallery_photo_id=photo.file_id)
    await state.set_state("waiting_for_gallery_description")
    await message.answer(
        "📝 <b>Добавьте описание к фото</b>\n\n"
        "Отправьте текст или нажмите «Пропустить».\n\n"
        "⏭️ Пропустить - /skip",
        parse_mode="HTML"
    )

@router.message(lambda message: message.text == "/skip", StateFilter="waiting_for_gallery_description")
async def skip_gallery_description(message: types.Message, state: FSMContext):
    """Пропуск описания"""
    data = await state.get_data()
    photo_id = data.get('gallery_photo_id')
    
    await add_gallery_photo(photo_id, "", message.from_user.id)
    
    await state.clear()
    await message.answer(
        "✅ <b>Фото добавлено в галерею!</b>\n\n"
        "Описание: нет",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@router.message(StateFilter("waiting_for_gallery_description"))
async def save_gallery_description(message: types.Message, state: FSMContext):
    """Сохранение описания"""
    data = await state.get_data()
    photo_id = data.get('gallery_photo_id')
    
    await add_gallery_photo(photo_id, message.text, message.from_user.id)
    
    await state.clear()
    await message.answer(
        f"✅ <b>Фото добавлено в галерею!</b>\n\n"
        f"Описание: {message.text}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

@router.callback_query(lambda c: c.data == "delete_gallery_photo")
async def delete_gallery_photo_prompt(callback: types.CallbackQuery):
    """Запрос ID фото для удаления"""
    if not await is_admin(callback.from_user.id):
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
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return
    
    photo_id = int(message.text)
    success = await delete_gallery_photo(photo_id)
    
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
    if not await is_super_admin(message.from_user.id):
        await message.answer("❌ Только для супер-админа.")
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

@router.message(lambda message: message.text == "/skip", StateFilter(GiftStates.waiting_for_gift_description))
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

@router.message(lambda message: message.text == "/skip", StateFilter(GiftStates.waiting_for_gift_icon))
async def skip_gift_icon(message: types.Message, state: FSMContext):
    await state.update_data(gift_icon="🎁")
    data = await state.get_data()
    
    gift_id = await add_gift(
        name=data['gift_name'],
        price=data['gift_price'],
        description=data.get('gift_description', ''),
        icon=data.get('gift_icon', '🎁')
    )
    
    await state.clear()
    await message.answer(
        f"✅ <b>Подарок добавлен!</b>\n\n"
        f"🎁 {data['gift_name']}\n"
        f"💰 {data['gift_price']}₽\n"
        f"📝 {data.get('gift_description', 'Без описания')}\n"
        f"🆔 ID: {gift_id}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

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
    
    gift_id = await add_gift(
        name=data['gift_name'],
        price=data['gift_price'],
        description=data.get('gift_description', ''),
        icon=data.get('gift_icon', '🎁')
    )
    
    await state.clear()
    await message.answer(
        f"✅ <b>Подарок добавлен!</b>\n\n"
        f"{icon} {data['gift_name']}\n"
        f"💰 {data['gift_price']}₽\n"
        f"📝 {data.get('gift_description', 'Без описания')}\n"
        f"🆔 ID: {gift_id}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )

# ============ ТОП ГЕРОЕВ (АДМИН) ============

@router.message(lambda message: message.text == "🏆 Топ героев (админ)")
async def admin_top_heroes(message: types.Message):
    """Просмотр топа героев для админа"""
    if not await is_admin(message.from_user.id):
        await message.answer("❌ Нет доступа.")
        return
    
    from database import get_top_heroes
    heroes = await get_top_heroes(limit=20)
    
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

# ============ ВОЗВРАТ В АДМИНКУ ============

@router.callback_query(lambda c: c.data == "back_to_admin")
async def back_to_admin(callback: types.CallbackQuery):
    """Возврат в админ-панель"""
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет доступа!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🛠️ <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()

# ============ ОТМЕНА ============

@router.message(lambda message: message.text == "/cancel")
async def cancel_action(message: types.Message, state: FSMContext):
    """Отмена текущего действия"""
    await state.clear()
    if await is_admin(message.from_user.id):
        await message.answer("❌ Действие отменено.", reply_markup=get_admin_keyboard())
    else:
        await message.answer("❌ Действие отменено.", reply_markup=get_main_keyboard())
