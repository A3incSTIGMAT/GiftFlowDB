import logging
import asyncio
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import (
    ADMIN_IDS, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, PROFIT_SPLIT,
    CHANNEL_ID, TWITCH_URL, INSTAGRAM_URL
)
from database import (
    get_all_transactions, add_gallery_photo, get_gallery_photos,
    get_stats, add_gift
)
from keyboards import get_admin_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Временные хранилища
waiting_for_gift = {}
waiting_for_post = {}


async def delete_message_after_delay(message: types.Message, delay: int = 30):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass


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


@router.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return
    
    action = callback.data.split("_")[1]
    
    if action == "orders":
        transactions = await get_all_transactions(limit=20)
        if not transactions:
            await callback.message.answer("📦 Заказов пока нет")
            return
        text = "📦 <b>Последние заказы:</b>\n\n"
        for t in transactions[:10]:
            username = t.get('username', 'нет')
            text += f"💰 {t['amount']}₽ | {t['gift_name']} | @{username}\n"
        await callback.message.answer(text, parse_mode="HTML")
    
    elif action == "stats":
        if callback.from_user.id != SUPER_ADMIN_ID:
            await callback.answer("❌ Только для супер-админа", show_alert=True)
            return
        stats = await get_stats()
        total_amount = stats['total_amount']
        lana_share = total_amount * PROFIT_SPLIT['lana']
        admin_share = total_amount * PROFIT_SPLIT['admin']
        dev_share = total_amount * PROFIT_SPLIT['development']
        tax_share = total_amount * PROFIT_SPLIT['tax']
        await callback.message.answer(
            f"📊 <b>Полная статистика</b>\n\n"
            f"📦 Заказов: {stats['total_orders']}\n"
            f"💰 Общий оборот: {int(total_amount)}₽\n"
            f"👥 Пользователей: {stats['total_users']}\n\n"
            f"📈 <b>Распределение дохода:</b>\n"
            f"👤 Лана (47%): {int(lana_share)}₽\n"
            f"👤 Админ (28%): {int(admin_share)}₽\n"
            f"🚀 Развитие (19%): {int(dev_share)}₽\n"
            f"📋 Налог (6%): {int(tax_share)}₽",
            parse_mode="HTML"
        )
    
    elif action == "gallery":
        await callback.message.answer(
            "📸 <b>Галерея фото</b>\n\n"
            "Отправь мне фото с подписью — я добавлю его в галерею.\n\n"
            "Пример: фото + подпись 'Красивое фото со стрима'",
            parse_mode="HTML"
        )
    
    elif action == "add_gift":
        if callback.from_user.id not in [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]:
            await callback.answer("❌ Только для админов", show_alert=True)
            return
        waiting_for_gift[callback.from_user.id] = True
        await callback.message.answer(
            "🎁 <b>Добавление нового подарка</b>\n\n"
            "Отправь данные в формате:\n\n"
            "<code>Название | Цена | Описание | Иконка</code>\n\n"
            "Пример:\n"
            "<code>🍕 Пицца | 500 | Вкусная пицца | 🍕</code>\n\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )
    
    elif action == "create_post":
        if callback.from_user.id not in ADMIN_IDS:
            await callback.answer("❌ Только для админов", show_alert=True)
            return
        waiting_for_post[callback.from_user.id] = {"stage": "text"}
        await callback.message.answer(
            "📢 <b>Создание поста — Шаг 1 из 2</b>\n\n"
            "✏️ <b>Напиши текст поста</b>\n\n"
            "Ссылки на Twitch, Instagram и бот добавятся автоматически.\n\n"
            "❌ Отмена: /cancel",
            parse_mode="HTML"
        )
        await callback.answer()
    
    await callback.answer()


@router.message(F.text & F.from_user.id.in_(ADMIN_IDS))
async def handle_add_gift(message: types.Message):
    if not waiting_for_gift.get(message.from_user.id):
        return
    try:
        parts = message.text.split("|")
        if len(parts) < 3:
            await message.answer("❌ Неправильный формат!\n\nОтправь: <code>Название | Цена | Описание | Иконка</code>", parse_mode="HTML")
            return
        name = parts[0].strip()
        price = int(parts[1].strip())
        description = parts[2].strip() if len(parts) > 2 else ""
        icon = parts[3].strip() if len(parts) > 3 else "🎁"
        success = await add_gift(name, price, description, icon)
        if success:
            await message.answer(f"✅ <b>Подарок добавлен!</b>\n\n{icon} {name} | {price}₽", parse_mode="HTML")
        else:
            await message.answer("❌ Ошибка при добавлении подарка.")
    except Exception as e:
        await message.answer("❌ Ошибка формата. Пример: <code>🍕 Пицца | 500 | Вкусная пицца | 🍕</code>", parse_mode="HTML")
    finally:
        waiting_for_gift.pop(message.from_user.id, None)


@router.message(F.text & F.from_user.id.in_(ADMIN_IDS))
async def handle_post_text(message: types.Message):
    post_data = waiting_for_post.get(message.from_user.id)
    if not post_data or post_data.get("stage") != "text":
        return
    waiting_for_post[message.from_user.id] = {"stage": "photo", "text": message.text}
    await message.answer(
        "📢 <b>Создание поста — Шаг 2 из 2</b>\n\n"
        "📸 <b>Отправь фото для поста</b>\n\n"
        "✅ <b>/skip</b> — пропустить фото\n"
        "❌ <b>/cancel</b> — отменить",
        parse_mode="HTML"
    )


@router.message(Command("skip"))
async def skip_photo(message: types.Message):
    post_data = waiting_for_post.get(message.from_user.id)
    if not post_data or post_data.get("stage") != "photo":
        return
    await show_ready_post(message, post_data["text"], None)
    waiting_for_post.pop(message.from_user.id, None)


@router.message(F.photo & F.from_user.id.in_(ADMIN_IDS))
async def handle_post_photo(message: types.Message):
    post_data = waiting_for_post.get(message.from_user.id)
    if not post_data or post_data.get("stage") != "photo":
        return
    photo = message.photo[-1]
    await show_ready_post(message, post_data["text"], photo.file_id)
    waiting_for_post.pop(message.from_user.id, None)


async def show_ready_post(message: types.Message, text: str, photo_id: str = None):
    post_text = f"{text}\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    post_text += f"📺 <b>Twitch:</b> {TWITCH_URL}\n"
    post_text += f"📷 <b>Instagram:</b> {INSTAGRAM_URL}\n"
    post_text += f"💳 <b>Поддержать:</b> /start\n\n"
    post_text += f"🎁 <b>Подарки стримерше:</b> @{message.bot.username}"
    
    buttons_help = (
        f"\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔘 <b>КАК ДОБАВИТЬ КНОПКИ:</b>\n\n"
        f"1️⃣ Нажми <b>«Добавить кнопку»</b>\n"
        f"2️⃣ Добавь кнопки:\n\n"
        f"📺 <b>Кнопка 1:</b> Текст <code>Twitch</code> → ссылка <code>{TWITCH_URL}</code>\n"
        f"📷 <b>Кнопка 2:</b> Текст <code>Instagram</code> → ссылка <code>{INSTAGRAM_URL}</code>\n"
        f"🎁 <b>Кнопка 3:</b> Текст <code>Подарки</code> → ссылка <code>https://t.me/{message.bot.username}?start</code>\n\n"
        f"3️⃣ Нажми <b>«Отправить»</b>"
    )
    
    full = post_text + buttons_help
    
    if photo_id:
        await message.answer_photo(photo_id, caption=full, parse_mode="HTML")
    else:
        await message.answer(full, parse_mode="HTML")
    
    await message.answer(
        "✅ <b>Готово!</b>\n\n📋 Скопируй текст выше и вставь в канал.\n🔘 Добавь кнопки по инструкции.\n📢 Нажми «Отправить».",
        parse_mode="HTML"
    )


@router.message(F.photo)
async def handle_gallery_photo(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if waiting_for_post.get(message.from_user.id, {}).get("stage") == "photo":
        return
    photo = message.photo[-1]
    await add_gallery_photo(photo.file_id, message.caption or "", message.from_user.id)
    msg = await message.answer("✅ Фото добавлено в галерею!", parse_mode="HTML")
    asyncio.create_task(delete_message_after_delay(msg, 30))


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
    for photo_id, caption, created_at in photos[:5]:
        await message.answer_photo(photo_id, caption=f"📅 {created_at}\n{caption or 'без подписи'}", parse_mode="HTML")


@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Только для супер-админа")
        return
    stats = await get_stats()
    total = stats['total_amount']
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"📦 Заказов: {stats['total_orders']}\n"
        f"💰 Оборот: {int(total)}₽\n"
        f"👥 Пользователей: {stats['total_users']}",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    if message.from_user.id in waiting_for_gift:
        waiting_for_gift.pop(message.from_user.id)
        await message.answer("❌ Добавление подарка отменено.")
    elif message.from_user.id in waiting_for_post:
        waiting_for_post.pop(message.from_user.id)
        await message.answer("❌ Создание поста отменено.")
    else:
        await message.answer("❌ Нет активных действий.")
