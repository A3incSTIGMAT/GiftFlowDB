import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import (
    ADMIN_IDS, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID,
    PROFIT_SPLIT, CHANNEL_ID, TWITCH_URL, INSTAGRAM_URL, DONATEPAY_URL
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


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Вход в админ-панель по команде /admin"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    admin_kb = await get_admin_keyboard(message.from_user.id)
    
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выбери раздел управления:",
        parse_mode="HTML",
        reply_markup=admin_kb
    )


@router.callback_query(F.data.startswith("admin_"))
async def admin_actions(callback: types.CallbackQuery):
    """Обработка кнопок админ-панели"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return
    
    action = callback.data.split("_")[1]
    
    # === ЗАКАЗЫ ===
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
    
    # === СТАТИСТИКА ===
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
    
    # === ГАЛЕРЕЯ ===
    elif action == "gallery":
        await callback.message.answer(
            "📸 <b>Галерея фото</b>\n\n"
            "Отправь мне фото с подписью в одном сообщении — я добавлю его в галерею.\n\n"
            "Пример: фото + подпись 'Красивое фото со стрима'",
            parse_mode="HTML"
        )
    
    # === ДОБАВИТЬ ПОДАРОК ===
    elif action == "add_gift":
        if callback.from_user.id not in [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]:
            await callback.answer("❌ Только для админов", show_alert=True)
            return
        
        waiting_for_gift[callback.from_user.id] = True
        
        await callback.message.answer(
            "🎁 <b>Добавление нового подарка</b>\n\n"
            "Отправь мне данные в формате:\n\n"
            "<code>Название | Цена | Описание | Иконка</code>\n\n"
            "Пример:\n"
            "<code>🍕 Пицца | 500 | Вкусная пицца для стримерши | 🍕</code>\n\n"
            "⚠️ Цена — только число (без ₽)\n"
            "Иконка — любой эмодзи",
            parse_mode="HTML"
        )
    
    # === СОЗДАТЬ ПОСТ ===
    elif action == "create_post":
        if callback.from_user.id not in [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]:
            await callback.answer("❌ Только для админов", show_alert=True)
            return
        
        from keyboards import get_post_options_keyboard
        await callback.message.answer(
            "📢 <b>Создание поста</b>\n\n"
            "Выбери откуда взять фото:\n\n"
            "📸 <b>Из галереи</b> — выбрать ранее загруженное фото\n"
            "🆕 <b>Новое фото</b> — загрузить сейчас",
            parse_mode="HTML",
            reply_markup=await get_post_options_keyboard()
        )
    
    await callback.answer()


# === ОБРАБОТКА ДОБАВЛЕНИЯ ПОДАРКА ===
@router.message(F.text & F.from_user.id.in_(ADMIN_IDS))
async def handle_add_gift(message: types.Message):
    """Обработка добавления подарка"""
    if not waiting_for_gift.get(message.from_user.id):
        return
    
    try:
        parts = message.text.split("|")
        if len(parts) < 3:
            await message.answer(
                "❌ Неправильный формат!\n\n"
                "Отправь: <code>Название | Цена | Описание | Иконка</code>\n\n"
                "Пример: <code>🍕 Пицца | 500 | Вкусная пицца | 🍕</code>",
                parse_mode="HTML"
            )
            return
        
        name = parts[0].strip()
        price_str = parts[1].strip()
        description = parts[2].strip() if len(parts) > 2 else ""
        icon = parts[3].strip() if len(parts) > 3 else "🎁"
        
        try:
            price = int(price_str)
        except ValueError:
            await message.answer("❌ Цена должна быть числом! Пример: <code>500</code>", parse_mode="HTML")
            return
        
        success = await add_gift(name, price, description, icon)
        
        if success:
            await message.answer(
                f"✅ <b>Подарок добавлен!</b>\n\n"
                f"{icon} <b>{name}</b>\n"
                f"💰 Цена: {price}₽\n"
                f"📝 {description}\n\n"
                f"Подарок появился в каталоге!",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Ошибка при добавлении подарка. Попробуй позже.")
        
    except Exception as e:
        logger.error(f"Ошибка добавления подарка: {e}")
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз.")
    
    finally:
        waiting_for_gift.pop(message.from_user.id, None)


# === СОЗДАНИЕ ПОСТА ===
@router.callback_query(F.data == "post_from_gallery")
async def post_from_gallery(callback: types.CallbackQuery):
    """Создание поста из галереи"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return
    
    photos = await get_gallery_photos(limit=20)
    if not photos:
        await callback.message.answer(
            "📸 Галерея пуста. Сначала загрузи фото через админ-панель.",
            parse_mode="HTML"
        )
        return
    
    from keyboards import get_gallery_choice_keyboard
    await callback.message.answer(
        "📸 <b>Выбери фото из галереи:</b>\n\n"
        "Нажми на кнопку с нужным фото:",
        parse_mode="HTML",
        reply_markup=await get_gallery_choice_keyboard(photos)
    )
    await callback.answer()


@router.callback_query(F.data == "post_new_photo")
async def post_new_photo(callback: types.CallbackQuery):
    """Создание поста с новым фото"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return
    
    waiting_for_post[callback.from_user.id] = {"stage": "photo"}
    
    await callback.message.answer(
        "📸 <b>Создание поста</b>\n\n"
        "Отправь мне фото для поста:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("select_photo_"))
async def select_photo_for_post(callback: types.CallbackQuery):
    """Выбор фото из галереи"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return
    
    photo_id = callback.data.split("_")[2]
    
    waiting_for_post[callback.from_user.id] = {
        "stage": "text",
        "photo_id": photo_id
    }
    
    await callback.message.answer(
        "📝 <b>Создание поста</b>\n\n"
        "Отправь текст поста (без ссылок, они добавятся автоматически):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.photo & F.from_user.id.in_(ADMIN_IDS))
async def handle_post_photo(message: types.Message):
    """Обработка загрузки фото для поста"""
    if waiting_for_post.get(message.from_user.id, {}).get("stage") != "photo":
        return
    
    photo = message.photo[-1]
    
    waiting_for_post[message.from_user.id] = {
        "stage": "text",
        "photo_id": photo.file_id
    }
    
    await message.answer(
        "📝 <b>Создание поста</b>\n\n"
        "Отправь текст поста (без ссылок, они добавятся автоматически):",
        parse_mode="HTML"
    )


@router.message(F.text & F.from_user.id.in_(ADMIN_IDS))
async def handle_post_text(message: types.Message):
    """Обработка текста поста и публикация"""
    post_data = waiting_for_post.get(message.from_user.id)
    if not post_data or post_data.get("stage") != "text":
        return
    
    if not CHANNEL_ID:
        await message.answer(
            "❌ Канал не настроен. Добавь переменную CHANNEL_ID в настройках Amvera.\n\n"
            "Пример: CHANNEL_ID = @lanatwitchh",
            parse_mode="HTML"
        )
        waiting_for_post.pop(message.from_user.id, None)
        return
    
    photo_id = post_data.get("photo_id")
    text = message.text
    
    # Формируем пост с ссылками
    post_text = f"{text}\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    post_text += f"📺 <b>Twitch:</b> {TWITCH_URL}\n"
    post_text += f"📷 <b>Instagram:</b> {INSTAGRAM_URL}\n"
    post_text += f"💳 <b>DonatePay:</b> {DONATEPAY_URL}\n\n"
    post_text += f"🎁 <b>Поддержать:</b> https://t.me/{message.bot.username}?start"
    
    # Кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📺 Twitch", url=TWITCH_URL),
            InlineKeyboardButton(text="📷 Instagram", url=INSTAGRAM_URL),
        ],
        [
            InlineKeyboardButton(text="💳 DonatePay", url=DONATEPAY_URL),
            InlineKeyboardButton(text="🎁 Подарки", url=f"https://t.me/{message.bot.username}?start"),
        ]
    ])
    
    try:
        if photo_id:
            await message.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo_id,
                caption=post_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await message.bot.send_message(
                chat_id=CHANNEL_ID,
                text=post_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        
        await message.answer(
            f"✅ <b>Пост опубликован в канале!</b>\n\n"
            f"📢 Канал: {CHANNEL_ID}\n"
            f"📝 Текст: {text[:100]}{'...' if len(text) > 100 else ''}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка публикации поста: {e}")
        error_msg = str(e)
        if "chat not found" in error_msg.lower():
            await message.answer(
                f"❌ Канал не найден. Убедись, что:\n\n"
                f"1. Бот добавлен в канал {CHANNEL_ID} как администратор\n"
                f"2. ID канала указан правильно\n\n"
                f"Текущий CHANNEL_ID: <code>{CHANNEL_ID}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ Ошибка публикации: {error_msg[:200]}\n\n"
                f"Убедись, что бот добавлен в канал как администратор.",
                parse_mode="HTML"
            )
    
    finally:
        waiting_for_post.pop(message.from_user.id, None)


@router.message(F.photo)
async def handle_gallery_photo(message: types.Message):
    """Обработка загрузки фото в галерею"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только для админов")
        return
    
    # Если это процесс создания поста — не добавляем в галерею
    if waiting_for_post.get(message.from_user.id, {}).get("stage") == "photo":
        return
    
    photo = message.photo[-1]
    caption = message.caption or ""
    
    await add_gallery_photo(photo.file_id, caption, message.from_user.id)
    
    await message.answer(
        f"✅ Фото добавлено в галерею!\n"
        f"📝 Подпись: {caption if caption else 'без подписи'}",
        parse_mode="HTML"
    )


@router.message(Command("gallery"))
async def show_gallery(message: types.Message):
    """Показать галерею фото"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    photos = await get_gallery_photos(limit=10)
    if not photos:
        await message.answer("📸 Галерея пуста. Загрузи фото через админ-панель.")
        return
    
    await message.answer("📸 <b>Последние фото в галерее:</b>", parse_mode="HTML")
    
    for photo_id, caption, created_at in photos[:5]:
        await message.answer_photo(
            photo_id,
            caption=f"📅 {created_at}\n{caption if caption else 'без подписи'}",
            parse_mode="HTML"
        )


@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Быстрая статистика"""
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Только для супер-админа")
        return
    
    stats = await get_stats()
    total_amount = stats['total_amount']
    
    lana_share = total_amount * PROFIT_SPLIT['lana']
    admin_share = total_amount * PROFIT_SPLIT['admin']
    dev_share = total_amount * PROFIT_SPLIT['development']
    tax_share = total_amount * PROFIT_SPLIT['tax']
    
    await message.answer(
        f"📊 <b>Быстрая статистика</b>\n\n"
        f"📦 Заказов: {stats['total_orders']}\n"
        f"💰 Оборот: {int(total_amount)}₽\n"
        f"👥 Пользователей: {stats['total_users']}\n\n"
        f"📈 <b>Распределение:</b>\n"
        f"👤 Лана: {int(lana_share)}₽\n"
        f"👤 Админ: {int(admin_share)}₽\n"
        f"🚀 Развитие: {int(dev_share)}₽\n"
        f"📋 Налог: {int(tax_share)}₽",
        parse_mode="HTML"
    )
