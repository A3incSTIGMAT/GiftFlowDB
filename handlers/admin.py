import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from config import SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, ADMIN_IDS, CHANNEL_ID
from database import (
    is_admin, is_super_admin, add_admin, remove_admin, get_all_admins,
    get_pending_transactions, update_transaction_status, get_all_transactions,
    add_gift, get_gallery_photos, add_gallery_photo,
    delete_gallery_photo, get_stats, log_admin_action,
    get_top_heroes, update_top_heroes
)
from keyboards import get_admin_keyboard, get_cancel_keyboard, get_confirm_post_keyboard, get_main_keyboard

logger = logging.getLogger(__name__)
router = Router()

# ============ FSM СОСТОЯНИЯ ============

class CreatePostStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    preview = State()

class AddGiftStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_icon = State()

# ============ ГЛАВНАЯ АДМИН-ПАНЕЛЬ ============

@router.message(lambda message: message.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ У вас нет доступа к админ-панели.", reply_markup=get_main_keyboard())
        return
    
    keyboard = get_admin_keyboard()
    await message.answer(
        "🛠️ <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

# ============ УПРАВЛЕНИЕ ЗАКАЗАМИ ============

@router.message(lambda message: message.text == "📦 Управление заказами")
async def manage_orders(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    transactions = await get_pending_transactions(limit=20)
    
    if not transactions:
        await message.answer("📦 <b>Нет ожидающих заказов</b>\n\nВсе заказы обработаны.", parse_mode="HTML")
        return
    
    text = "📦 <b>Ожидают подтверждения:</b>\n\n"
    for t in transactions[:10]:
        text += (
            f"┌ <b>Заказ #{t['id']}</b>\n"
            f"├ 🎁 {t['gift_name']}\n"
            f"├ 💰 {t['amount']}₽\n"
            f"├ 👤 @{t.get('username') or t['user_id']}\n"
            f"├ 💳 {t.get('payment_method', 'не указан')}\n"
            f"├ 🕐 {t['created_at'][:16]}\n"
            f"└ ✅ <code>/approve {t['id']}</code>\n\n"
        )
    
    text += "\n💡 <i>Используй команду /approve [номер_заказа] для подтверждения</i>"
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text and message.text.startswith("/approve"))
async def approve_order(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ Используй: <code>/approve 123</code>", parse_mode="HTML")
        return
    
    try:
        transaction_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID заказа должен быть числом.")
        return
    
    transactions = await get_all_transactions(limit=100)
    transaction = next((t for t in transactions if t['id'] == transaction_id), None)
    
    if not transaction:
        await message.answer(f"❌ Заказ #{transaction_id} не найден.")
        return
    
    if transaction['status'] == 'paid':
        await message.answer(f"✅ Заказ #{transaction_id} уже подтверждён.")
        return
    
    await update_transaction_status(transaction_id, 'paid', confirmed_by=user_id)
    await log_admin_action(user_id, "approve_order", f"Заказ #{transaction_id}")
    
    position = await update_top_heroes(transaction['user_id'], transaction['amount'], transaction.get('username'))
    
    try:
        user_text = f"✅ <b>Ваш заказ #{transaction_id} подтверждён!</b>\n\n🎁 {transaction['gift_name']}\n💰 Сумма: {transaction['amount']}₽\n\n"
        if position:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            user_text += f"{medals.get(position, '🎖️')} <b>Вы в топ-{position} героев!</b>\n\n"
        user_text += "❤️ Спасибо за поддержку Ланы!"
        await message.bot.send_message(transaction['user_id'], user_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")
    
    if transaction['amount'] >= 5000:
        try:
            channel_text = f"🎉 <b>Новый донат!</b>\n\n@{transaction.get('username') or 'Аноним'} подарил(а) {transaction['gift_name']} на {transaction['amount']}₽\n❤️ Спасибо за поддержку!"
            await message.bot.send_message(CHANNEL_ID, channel_text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка отправки в канал: {e}")
    
    await message.answer(f"✅ Заказ #{transaction_id} подтверждён!\nПользователь уведомлён.\nТоп героев обновлён.", parse_mode="HTML")

# ============ УПРАВЛЕНИЕ ГАЛЕРЕЕЙ ============

@router.message(lambda message: message.text == "🖼️ Управление галереей")
async def manage_gallery(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    photos = await get_gallery_photos(limit=10)
    
    if not photos:
        await message.answer("🖼️ <b>Галерея пуста</b>\n\nДобавьте фото командой /add_photo", parse_mode="HTML")
        return
    
    text = "🖼️ <b>Галерея</b>\n\n"
    for p in photos[:10]:
        text += f"┌ <b>ID:</b> {p['id']}\n├ 📝 {p['description'][:30] if p['description'] else 'без описания'}\n└ 🗑️ <code>/del_photo {p['id']}</code>\n\n"
    
    text += "\n💡 <i>Добавить фото: /add_photo [описание]\nУдалить фото: /del_photo [ID]</i>"
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text and message.text.startswith("/add_photo"))
async def add_photo_command(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    await message.answer("📸 Отправьте фото для добавления в галерею.\n\nДля отмены нажмите ❌ Отмена", reply_markup=get_cancel_keyboard())

@router.message(lambda message: message.photo and message.text != "❌ Отмена")
async def receive_photo_for_gallery(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    photo = message.photo[-1]
    file_id = photo.file_id
    caption = message.caption or ""
    
    await add_gallery_photo(file_id, caption, user_id)
    await log_admin_action(user_id, "add_photo", f"Добавлено фото: {caption[:50]}")
    
    await message.answer(f"✅ Фото добавлено в галерею!\n📝 Описание: {caption if caption else 'нет'}", reply_markup=get_admin_keyboard())

@router.message(lambda message: message.text and message.text.startswith("/del_photo"))
async def delete_photo_command(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ Используй: <code>/del_photo 123</code>", parse_mode="HTML")
        return
    
    try:
        photo_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID фото должен быть числом.")
        return
    
    success = await delete_gallery_photo(photo_id)
    
    if success:
        await log_admin_action(user_id, "delete_photo", f"Удалено фото #{photo_id}")
        await message.answer(f"✅ Фото #{photo_id} удалено из галереи.")
    else:
        await message.answer(f"❌ Фото #{photo_id} не найдено.")

# ============ СОЗДАНИЕ ПОСТОВ ============

@router.message(lambda message: message.text == "✏️ Создать пост")
async def create_post_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    await state.set_state(CreatePostStates.waiting_for_text)
    await message.answer(
        "✏️ <b>Создание поста</b>\n\n"
        "Отправьте <b>текст</b> поста.\n"
        "Поддерживается HTML разметка.\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@router.message(CreatePostStates.waiting_for_text)
async def receive_post_text(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание поста отменено.", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(post_text=message.text)
    await state.set_state(CreatePostStates.waiting_for_photo)
    
    await message.answer(
        "📸 Теперь отправьте <b>фото</b> для поста.\n"
        "Или нажмите «Пропустить», чтобы опубликовать без фото.",
        parse_mode="HTML",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="⏩ Пропустить")], [types.KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )

@router.message(CreatePostStates.waiting_for_photo)
async def receive_post_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Создание поста отменено.", reply_markup=get_admin_keyboard())
        return
    
    data = await state.get_data()
    post_text = data.get('post_text', '')
    photo_file_id = None
    
    if message.text == "⏩ Пропустить":
        photo_file_id = None
    elif message.photo:
        photo_file_id = message.photo[-1].file_id
    else:
        await message.answer("❌ Пожалуйста, отправьте фото или нажмите «Пропустить».")
        return
    
    await state.update_data(photo_file_id=photo_file_id)
    await state.set_state(CreatePostStates.preview)
    
    preview_text = f"📝 <b>Предпросмотр поста</b>\n\n{post_text}\n\n✅ <i>Всё верно?</i>"
    
    if photo_file_id:
        await message.answer_photo(
            photo_file_id,
            caption=preview_text,
            parse_mode="HTML",
            reply_markup=get_confirm_post_keyboard()
        )
    else:
        await message.answer(
            preview_text,
            parse_mode="HTML",
            reply_markup=get_confirm_post_keyboard()
        )

@router.callback_query(lambda c: c.data == "confirm_post")
async def confirm_post(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("❌ Нет доступа.")
        return
    
    data = await state.get_data()
    post_text = data.get('post_text', '')
    photo_file_id = data.get('photo_file_id')
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    post_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 Twitch", url="https://twitch.tv/lana")],
        [InlineKeyboardButton(text="📷 Instagram", url="https://instagram.com/lana")],
        [InlineKeyboardButton(text="🎁 Подарки", url="https://t.me/GiftFlowDB_bot")],
        [InlineKeyboardButton(text="🆘 Помощь", callback_data="help")]
    ])
    
    try:
        if photo_file_id:
            await callback.bot.send_photo(
                CHANNEL_ID,
                photo_file_id,
                caption=post_text,
                parse_mode="HTML",
                reply_markup=post_keyboard
            )
        else:
            await callback.bot.send_message(
                CHANNEL_ID,
                post_text,
                parse_mode="HTML",
                reply_markup=post_keyboard
            )
        
        await log_admin_action(user_id, "create_post", f"Опубликован пост")
        await callback.message.edit_text("✅ Пост успешно опубликован в канале!")
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка публикации поста: {e}")
        await callback.message.edit_text(f"❌ Ошибка публикации: {e}")
    
    await callback.answer()

@router.callback_query(lambda c: c.data == "cancel_post")
async def cancel_post(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Создание поста отменено.")
    await callback.answer()

# ============ ДОБАВЛЕНИЕ ПОДАРКОВ ============

@router.message(lambda message: message.text == "➕ Добавить подарок")
async def add_gift_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not await is_super_admin(user_id):
        await message.answer("❌ Только для супер-админа.")
        return
    
    await state.set_state(AddGiftStates.waiting_for_name)
    await message.answer(
        "➕ <b>Добавление подарка</b>\n\n"
        "Введите <b>название</b> подарка:\n"
        "Например: <code>Именной стрим</code>\n\n"
        "Для отмены нажмите ❌ Отмена",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )

@router.message(AddGiftStates.waiting_for_name)
async def add_gift_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено.", reply_markup=get_admin_keyboard())
        return
    
    await state.update_data(name=message.text)
    await state.set_state(AddGiftStates.waiting_for_price)
    await message.answer("💰 Введите <b>цену</b> подарка в рублях (только число):", parse_mode="HTML")

@router.message(AddGiftStates.waiting_for_price)
async def add_gift_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено.", reply_markup=get_admin_keyboard())
        return
    
    try:
        price = int(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(price=price)
        await state.set_state(AddGiftStates.waiting_for_description)
        await message.answer("📝 Введите <b>описание</b> подарка (или нажмите «Пропустить»):", parse_mode="HTML")
    except ValueError:
        await message.answer("❌ Введите корректное число (больше 0).")

@router.message(AddGiftStates.waiting_for_description)
async def add_gift_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено.", reply_markup=get_admin_keyboard())
        return
    
    description = "" if message.text == "⏩ Пропустить" else message.text
    await state.update_data(description=description)
    await state.set_state(AddGiftStates.waiting_for_icon)
    await message.answer("🎨 Выберите <b>иконку</b> для подарка (один emoji):\nНапример: 🎁 🎮 🎥 💎\nИли нажмите «Пропустить» для стандартной 🎁", parse_mode="HTML")

@router.message(AddGiftStates.waiting_for_icon)
async def add_gift_icon(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Добавление отменено.", reply_markup=get_admin_keyboard())
        return
    
    icon = "🎁" if message.text == "⏩ Пропустить" else message.text.strip()
    
    data = await state.get_data()
    gift_id = await add_gift(data['name'], data['price'], data['description'], icon)
    
    await log_admin_action(message.from_user.id, "add_gift", f"Добавлен подарок: {data['name']}")
    
    await message.answer(
        f"✅ <b>Подарок добавлен!</b>\n\n"
        f"{icon} <b>{data['name']}</b>\n"
        f"💰 {data['price']}₽\n"
        f"📝 {data['description'] if data['description'] else 'нет описания'}\n\n"
        f"🆔 ID: {gift_id}",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()

# ============ СТАТИСТИКА ============

@router.message(lambda message: message.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    stats = await get_stats()
    pending = await get_pending_transactions(limit=1)
    top_heroes = await get_top_heroes(limit=3)
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b> {stats.get('total_users', 0)}\n"
        f"🎁 <b>Всего донатов:</b> {stats.get('total_donations', 0)}\n"
        f"💰 <b>Общая сумма:</b> {stats.get('total_amount', 0):,}₽\n"
        f"📅 <b>За этот месяц:</b> {stats.get('month_amount', 0):,}₽\n"
        f"⏳ <b>Ожидают:</b> {len(pending)} заказов\n\n"
    )
    
    if top_heroes:
        text += "🏆 <b>Топ-3 героев:</b>\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, hero in enumerate(top_heroes[:3]):
            username = hero.get('username') or f"user_{hero['user_id']}"
            text += f"{medals[i]} {username} — {hero['total_amount']:,}₽\n"
    
    text += f"\n📊 <i>Обновлено: {stats.get('updated_at', datetime.now()).strftime('%d.%m.%Y %H:%M')}</i>"
    
    await message.answer(text, parse_mode="HTML")

# ============ ТОП ГЕРОЕВ (АДМИН) ============

@router.message(lambda message: message.text == "🏆 Топ героев (админ)")
async def admin_top_heroes(message: types.Message):
    user_id = message.from_user.id
    if not await is_admin(user_id):
        await message.answer("❌ Нет доступа.")
        return
    
    heroes = await get_top_heroes(limit=20)
    
    if not heroes:
        await message.answer("🏆 Топ героев пока пуст.")
        return
    
    text = "🏆 <b>Топ героев канала</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    
    for i, hero in enumerate(heroes[:20]):
        medal = medals[i] if i < 3 else f"{i+1}."
        username = hero.get('username') or f"user_{hero['user_id']}"
        text += f"{medal} {username} — {hero['total_amount']:,}₽\n"
    
    await message.answer(text, parse_mode="HTML")

# ============ УПРАВЛЕНИЕ АДМИНАМИ ============

@router.message(lambda message: message.text == "👥 Управление админами")
async def manage_admins(message: types.Message):
    user_id = message.from_user.id
    if not await is_super_admin(user_id):
        await message.answer("❌ Только для супер-админа.")
        return
    
    admins = await get_all_admins()
    
    text = "👥 <b>Список администраторов</b>\n\n"
    text += f"👑 Супер-админ: {SUPER_ADMIN_ID}\n"
    text += f"🛠️ Менеджер: {SUPPORT_ADMIN_ID}\n\n"
    
    if admins:
        text += "<b>Дополнительные админы:</b>\n"
        for a in admins:
            text += f"└ @{a['username'] or a['user_id']} (ID: {a['user_id']})\n"
    else:
        text += "Нет дополнительных админов.\n"
    
    text += "\n💡 <i>Добавить: /add_admin [ID]\nУдалить: /remove_admin [ID]</i>"
    
    await message.answer(text, parse_mode="HTML")

@router.message(lambda message: message.text and message.text.startswith("/add_admin"))
async def add_admin_command(message: types.Message):
    user_id = message.from_user.id
    if not await is_super_admin(user_id):
        await message.answer("❌ Только для супер-админа.")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ Используй: <code>/add_admin 123456789</code>", parse_mode="HTML")
        return
    
    try:
        new_admin_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    
    if new_admin_id == SUPER_ADMIN_ID or new_admin_id == SUPPORT_ADMIN_ID:
        await message.answer("❌ Этот пользователь уже в списке главных админов.")
        return
    
    success = await add_admin(new_admin_id)
    
    if success:
        await log_admin_action(user_id, "add_admin", f"Добавлен админ {new_admin_id}")
        await message.answer(f"✅ Администратор {new_admin_id} добавлен.")
    else:
        await message.answer("❌ Ошибка добавления.")

@router.message(lambda message: message.text and message.text.startswith("/remove_admin"))
async def remove_admin_command(message: types.Message):
    user_id = message.from_user.id
    if not await is_super_admin(user_id):
        await message.answer("❌ Только для супер-админа.")
        return
    
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ Используй: <code>/remove_admin 123456789</code>", parse_mode="HTML")
        return
    
    try:
        admin_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    
    success = await remove_admin(admin_id)
    
    if success:
        await log_admin_action(user_id, "remove_admin", f"Удалён админ {admin_id}")
        await message.answer(f"✅ Администратор {admin_id} удалён.")
    else:
        await message.answer("❌ Администратор не найден.")
