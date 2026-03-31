import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, PROFIT_SPLIT, TWITCH_URL, INSTAGRAM_URL
from database import get_all_transactions, get_stats, add_gift, add_gallery_photo, get_gallery_photos
from keyboards import get_admin_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Хранилища состояний
waiting_for_gift = {}
waiting_for_post = {}


# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\nВыбери раздел управления:",
        parse_mode="HTML",
        reply_markup=await get_admin_keyboard(message.from_user.id)
    )


# ========== ОБРАБОТКА КНОПОК АДМИНКИ ==========
@router.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return

    action = callback.data.split("_", 1)[1]

    # === ЗАКАЗЫ ===
    if action == "orders":
        transactions = await get_all_transactions(limit=20)
        if not transactions:
            await callback.message.answer("📦 Заказов пока нет")
            return
        text = "📦 <b>Последние заказы:</b>\n\n"
        for t in transactions[:10]:
            text += f"💰 {t['amount']}₽ | {t['gift_name']} | @{t.get('username', 'нет')}\n"
        await callback.message.answer(text, parse_mode="HTML")

    # === СТАТИСТИКА (только супер-админ) ===
    elif action == "stats":
        if callback.from_user.id != SUPER_ADMIN_ID:
            await callback.answer("❌ Только для супер-админа", show_alert=True)
            return
        stats = await get_stats()
        total = stats['total_amount']
        await callback.message.answer(
            f"📊 <b>Статистика</b>\n\n"
            f"📦 Заказов: {stats['total_orders']}\n"
            f"💰 Оборот: {int(total)}₽\n"
            f"👥 Пользователей: {stats['total_users']}",
            parse_mode="HTML"
        )

    # === ГАЛЕРЕЯ ===
    elif action == "gallery":
        await callback.message.answer(
            "📸 <b>Галерея фото</b>\n\nОтправь фото с подписью — добавлю в галерею.\n"
            "Пример: фото + подпись 'Красивое фото со стрима'",
            parse_mode="HTML"
        )

    # === ДОБАВИТЬ ПОДАРОК (только админы) ===
    elif action == "add_gift":
        if callback.from_user.id not in (SUPER_ADMIN_ID, SUPPORT_ADMIN_ID):
            await callback.answer("❌ Только для админов", show_alert=True)
            return
        waiting_for_gift[callback.from_user.id] = True
        await callback.message.answer(
            "🎁 <b>Добавление подарка</b>\n\n"
            "Отправь данные в формате:\n"
            "<code>Название | Цена | Описание | Иконка</code>\n\n"
            "Пример:\n<code>🍕 Пицца | 500 | Вкусная пицца | 🍕</code>\n\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )

    # === СОЗДАТЬ ПОСТ ===
    elif action == "create_post":
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("❌ Только для админов", show_alert=True)
            return
        waiting_for_post[callback.from_user.id] = {"step": "text"}
        await callback.message.answer(
            "📢 <b>Создание поста — текст</b>\n\n"
            "✏️ Напиши текст поста (без ссылок, они добавятся сами).\n\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )

    await callback.answer()


# ========== ДОБАВЛЕНИЕ ПОДАРКА (текст) ==========
@router.message(F.text & F.from_user.id.in_(ADMIN_IDS))
async def add_gift_text(message: types.Message):
    if not waiting_for_gift.get(message.from_user.id):
        return
    try:
        parts = message.text.split("|")
        if len(parts) < 3:
            await message.answer("❌ Ошибка: нужно <code>Название | Цена | Описание | Иконка</code>", parse_mode="HTML")
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


# ========== СОЗДАНИЕ ПОСТА — ШАГ 1: ТЕКСТ ==========
@router.message(F.text & F.from_user.id.in_(ADMIN_IDS))
async def post_text_step(message: types.Message):
    state = waiting_for_post.get(message.from_user.id)
    if not state or state.get("step") != "text":
        return
    waiting_for_post[message.from_user.id] = {"step": "photo", "text": message.text}
    await message.answer(
        "📢 <b>Создание поста — фото</b>\n\n"
        "📸 Отправь фото (или /skip, чтобы пропустить)\n\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )


@router.message(Command("skip"))
async def skip_photo(message: types.Message):
    state = waiting_for_post.get(message.from_user.id)
    if not state or state.get("step") != "photo":
        return
    await finish_post(message, state["text"], None)
    waiting_for_post.pop(message.from_user.id, None)


@router.message(F.photo & F.from_user.id.in_(ADMIN_IDS))
async def post_photo_step(message: types.Message):
    state = waiting_for_post.get(message.from_user.id)
    if not state or state.get("step") != "photo":
        return
    photo = message.photo[-1]
    await finish_post(message, state["text"], photo.file_id)
    waiting_for_post.pop(message.from_user.id, None)


async def finish_post(message: types.Message, text: str, photo_id: str = None):
    post_text = f"{text}\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    post_text += f"📺 <b>Twitch</b>: {TWITCH_URL}\n"
    post_text += f"📷 <b>Instagram</b>: {INSTAGRAM_URL}\n"
    post_text += f"🎁 <b>Подарки</b>: @{message.bot.username}\n\n"
    post_text += "🔘 <b>Кнопки (добавь вручную):</b>\n"
    post_text += f"• Twitch: {TWITCH_URL}\n"
    post_text += f"• Instagram: {INSTAGRAM_URL}\n"
    post_text += f"• Подарки: https://t.me/{message.bot.username}?start"

    if photo_id:
        await message.answer_photo(photo_id, caption=post_text, parse_mode="HTML")
    else:
        await message.answer(post_text, parse_mode="HTML")

    await message.answer(
        "✅ <b>Готово!</b>\n\n"
        "📋 Скопируй текст выше и вставь в канал.\n"
        "🔘 Добавь кнопки по инструкции.\n"
        "📢 Нажми «Отправить».",
        parse_mode="HTML"
    )


# ========== ГАЛЕРЕЯ: ПРИЁМ ФОТО ==========
@router.message(F.photo)
async def gallery_photo(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if waiting_for_post.get(message.from_user.id, {}).get("step") == "photo":
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
        await message.answer("📸 Галерея пуста.")
        return
    await message.answer("📸 <b>Последние фото:</b>", parse_mode="HTML")
    for pid, caption, date in photos[:5]:
        await message.answer_photo(pid, caption=f"📅 {date}\n{caption or 'без подписи'}", parse_mode="HTML")


@router.message(Command("stats"))
async def stats_cmd(message: types.Message):
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Только для супер-админа")
        return
    stats = await get_stats()
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"📦 Заказов: {stats['total_orders']}\n"
        f"💰 Оборот: {stats['total_amount']}₽\n"
        f"👥 Пользователей: {stats['total_users']}",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cancel_action(message: types.Message):
    if message.from_user.id in waiting_for_gift:
        waiting_for_gift.pop(message.from_user.id)
        await message.answer("❌ Добавление подарка отменено.")
    elif message.from_user.id in waiting_for_post:
        waiting_for_post.pop(message.from_user.id)
        await message.answer("❌ Создание поста отменено.")
    else:
        await message.answer("❌ Нет активных действий.")
