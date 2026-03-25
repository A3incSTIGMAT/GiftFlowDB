import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from config import ADMIN_IDS, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, PROFIT_SPLIT, TWITCH_URL, INSTAGRAM_URL
from database import (
    get_all_transactions, add_gallery_photo, get_gallery_photos,
    get_stats, add_gift
)
from keyboards import get_admin_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Временные хранилища
waiting_for_gift = {}


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
    
    await callback.answer()


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


@router.message(F.photo)
async def handle_gallery_photo(message: types.Message):
    """Обработка загрузки фото в галерею"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только для админов")
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
