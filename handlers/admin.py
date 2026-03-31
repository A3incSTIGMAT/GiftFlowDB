import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from config import ADMIN_IDS, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, TWITCH_URL, INSTAGRAM_URL, CHANNEL_ID
from database import get_all_transactions, get_stats, add_gift, add_gallery_photo, get_gallery_photos
from keyboards import get_admin_keyboard

logger = logging.getLogger(__name__)
router = Router()

waiting_for_gift = {}
waiting_for_post = {}


# ========== АДМИН-ПАНЕЛЬ ==========
@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\nВыбери действие:",
        parse_mode="HTML",
        reply_markup=await get_admin_keyboard(message.from_user.id)
    )


# ========== ОБРАБОТКА КНОПОК ==========
@router.callback_query(F.data.startswith("admin_"))
async def admin_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    action = callback.data.split("_", 1)[1]

    if action == "orders":
        txns = await get_all_transactions(limit=20)
        if not txns:
            await callback.message.answer("📦 Заказов пока нет")
            return
        text = "📦 <b>Последние заказы:</b>\n\n"
        for t in txns[:10]:
            text += f"💰 {t['amount']}₽ | {t['gift_name']} | @{t.get('username', 'нет')}\n"
        await callback.message.answer(text, parse_mode="HTML")

    elif action == "stats":
        if user_id != SUPER_ADMIN_ID:
            await callback.answer("❌ Только супер-админ", show_alert=True)
            return
        stats = await get_stats()
        await callback.message.answer(
            f"📊 <b>Статистика</b>\n\n"
            f"📦 Заказов: {stats['total_orders']}\n"
            f"💰 Оборот: {stats['total_amount']}₽\n"
            f"👥 Пользователей: {stats['total_users']}",
            parse_mode="HTML"
        )

    elif action == "gallery":
        await callback.message.answer(
            "📸 <b>Галерея</b>\n\n"
            "Отправь фото с подписью — добавлю в галерею.\n"
            "Пример: фото + подпись 'Красивое фото со стрима'",
            parse_mode="HTML"
        )

    elif action == "add_gift":
        if user_id not in (SUPER_ADMIN_ID, SUPPORT_ADMIN_ID):
            await callback.answer("❌ Только админы", show_alert=True)
            return
        waiting_for_gift[user_id] = True
        await callback.message.answer(
            "🎁 <b>Добавление подарка</b>\n\n"
            "Формат: <code>Название | Цена | Описание | Иконка</code>\n"
            "Пример: <code>🍕 Пицца | 500 | Вкусная пицца | 🍕</code>\n\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )

    elif action == "create_post":
        waiting_for_post[user_id] = {"step": "text"}
        await callback.message.answer(
            "📢 <b>Создание поста — Шаг 1/3</b>\n\n"
            "✏️ Напиши текст поста\n\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )

    await callback.answer()


# ========== СОЗДАНИЕ ПОСТА — ТЕКСТ ==========
@router.message(F.text & F.from_user.id.in_(ADMIN_IDS))
async def post_text(message: types.Message):
    if waiting_for_gift.get(message.from_user.id):
        return

    state = waiting_for_post.get(message.from_user.id)
    if not state or state.get("step") != "text":
        return

    waiting_for_post[message.from_user.id] = {"step": "photo", "text": message.text}
    await message.answer(
        "📢 <b>Создание поста — Шаг 2/3</b>\n\n"
        "📸 Отправь фото (или /skip)\n\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )


# ========== ДОБАВЛЕНИЕ ПОДАРКА (ТЕКСТ) ==========
@router.message(F.text & F.from_user.id.in_(ADMIN_IDS))
async def add_gift_text(message: types.Message):
    if not waiting_for_gift.get(message.from_user.id):
        return
    try:
        parts = message.text.split("|")
        if len(parts) < 3:
            await message.answer("❌ Ошибка. Нужно: <code>Название | Цена | Описание | Иконка</code>", parse_mode="HTML")
            return
        name = parts[0].strip()
        price = int(parts[1].strip())
        desc = parts[2].strip()
        icon = parts[3].strip() if len(parts) > 3 else "🎁"
        await add_gift(name, price, desc, icon)
        await message.answer(f"✅ Подарок <b>{name}</b> добавлен!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        waiting_for_gift.pop(message.from_user.id, None)


# ========== /skip ==========
@router.message(Command("skip"))
async def skip_photo(message: types.Message):
    state = waiting_for_post.get(message.from_user.id)
    if not state or state.get("step") != "photo":
        return
    waiting_for_post[message.from_user.id] = {"step": "confirm", "text": state["text"], "photo_id": None}
    await show_confirm(message, state["text"], None)


# ========== ФОТО ДЛЯ ПОСТА ==========
@router.message(F.photo & F.from_user.id.in_(ADMIN_IDS))
async def post_photo(message: types.Message):
    state = waiting_for_post.get(message.from_user.id)
    if not state or state.get("step") != "photo":
        return
    photo = message.photo[-1]
    waiting_for_post[message.from_user.id] = {"step": "confirm", "text": state["text"], "photo_id": photo.file_id}
    await show_confirm(message, state["text"], photo.file_id)


# ========== ПОДТВЕРЖДЕНИЕ ПУБЛИКАЦИИ ==========
async def show_confirm(message: types.Message, text: str, photo_id: str = None):
    preview = f"📢 <b>Предпросмотр поста:</b>\n\n{text[:200]}..."
    if photo_id:
        await message.answer_photo(photo_id, caption=preview, parse_mode="HTML")
    else:
        await message.answer(preview, parse_mode="HTML")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="confirm_publish")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_publish")]
    ])
    await message.answer("Опубликовать пост в канале?", reply_markup=kb)


@router.callback_query(F.data == "confirm_publish")
async def confirm_publish(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    state = waiting_for_post.get(user_id)
    if not state or state.get("step") != "confirm":
        await callback.answer("❌ Нет поста для публикации")
        return

    text = state["text"]
    photo_id = state.get("photo_id")

    post_text = (
        f"{text}\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📺 <b>Twitch</b>: {TWITCH_URL}\n"
        f"📷 <b>Instagram</b>: {INSTAGRAM_URL}\n"
        f"🎁 <b>Подарки</b>: @{callback.bot.username}"
    )

    try:
        if photo_id:
            await callback.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo_id,
                caption=post_text,
                parse_mode="HTML"
            )
        else:
            await callback.bot.send_message(
                chat_id=CHANNEL_ID,
                text=post_text,
                parse_mode="HTML"
            )
        await callback.message.answer("✅ Пост опубликован в канале!")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка публикации: {e}")
    finally:
        waiting_for_post.pop(user_id, None)
    await callback.answer()


@router.callback_query(F.data == "cancel_publish")
async def cancel_publish(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in waiting_for_post:
        waiting_for_post.pop(user_id)
    await callback.message.answer("❌ Публикация отменена")
    await callback.answer()


# ========== ГАЛЕРЕЯ ==========
@router.message(F.photo)
async def save_gallery_photo(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if waiting_for_post.get(message.from_user.id, {}).get("step") in ("photo", "confirm"):
        return
    photo = message.photo[-1]
    await add_gallery_photo(photo.file_id, message.caption or "", message.from_user.id)
    await message.answer("✅ Фото добавлено в галерею!")


@router.message(Command("gallery"))
async def show_gallery(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    photos = await get_gallery_photos(limit=10)
    if not photos:
        await message.answer("📸 Галерея пуста")
        return
    await message.answer("📸 <b>Последние фото:</b>", parse_mode="HTML")
    for pid, caption, date in photos[:5]:
        await message.answer_photo(pid, caption=f"📅 {date}\n{caption or 'без подписи'}", parse_mode="HTML")


# ========== СТАТИСТИКА ==========
@router.message(Command("stats"))
async def stats_command(message: types.Message):
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Только супер-админ")
        return
    stats = await get_stats()
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"📦 Заказов: {stats['total_orders']}\n"
        f"💰 Оборот: {stats['total_amount']}₽\n"
        f"👥 Пользователей: {stats['total_users']}",
        parse_mode="HTML"
    )


# ========== /cancel ==========
@router.message(Command("cancel"))
async def cancel_action(message: types.Message):
    if message.from_user.id in waiting_for_gift:
        waiting_for_gift.pop(message.from_user.id)
        await message.answer("❌ Добавление подарка отменено")
    elif message.from_user.id in waiting_for_post:
        waiting_for_post.pop(message.from_user.id)
        await message.answer("❌ Создание поста отменено")
    else:
        await message.answer("❌ Нет активных действий")
