import logging
import asyncio
from datetime import datetime
from typing import Optional
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest
from config import (
    ADMIN_IDS, 
    SUPER_ADMIN_ID, 
    SUPPORT_ADMIN_ID, 
    TWITCH_URL, 
    INSTAGRAM_URL, 
    CHANNEL_ID, 
    BOT_TOKEN
)
from database import (
    get_all_transactions, 
    get_stats, 
    add_gift, 
    add_gallery_photo, 
    get_gallery_photos,
    log_admin_action,
    update_stats_cache
)
from keyboards import get_admin_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Глобальный бот
_bot: Bot = None


def set_bot(bot: Bot):
    """Установка экземпляра бота"""
    global _bot
    _bot = bot


def get_bot() -> Bot:
    """Получение экземпляра бота"""
    if _bot is None:
        raise RuntimeError("Bot not initialized. Call set_bot() first.")
    return _bot


# ========== КОНСТАНТЫ ==========
MAX_PREVIEW_LENGTH = 1000


# ========== FSM СОСТОЯНИЯ ==========
class AdminStates(StatesGroup):
    """Состояния админ-панели"""
    adding_gift = State()
    creating_post_text = State()
    creating_post_photo = State()
    creating_post_preview = State()
    editing_post_text = State()
    editing_post_photo = State()


# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
async def delete_message_safe(message: types.Message, delay: int = 3):
    """Безопасное удаление сообщения с задержкой"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except TelegramBadRequest as e:
        if "message can't be deleted" not in str(e).lower():
            logger.error(f"Ошибка удаления сообщения: {e}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка удаления: {e}")


async def send_temp_message(message: types.Message, text: str, delay: int = 5, **kwargs):
    """Отправка временного сообщения с автоудалением"""
    try:
        msg = await message.answer(text, **kwargs)
        asyncio.create_task(delete_message_safe(msg, delay))
        return msg
    except Exception as e:
        logger.error(f"Ошибка отправки временного сообщения: {e}")
        return None


def validate_channel_id(channel_id: str) -> bool:
    """Валидация ID канала"""
    if not channel_id:
        return False
    channel_id = str(channel_id).strip()
    return channel_id.startswith('-100') or channel_id.startswith('-')


async def check_bot_channel_permissions(channel_id: str) -> bool:
    """Проверка прав бота в канале"""
    try:
        bot = get_bot()
        member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.error(f"Ошибка проверки прав в канале: {e}")
        return False


# ========== ОБРАБОТЧИКИ КОМАНД ==========
@router.message(Command("cancel"))
async def cancel_action(message: types.Message, state: FSMContext):
    """Универсальная отмена действия"""
    await state.clear()
    await log_admin_action(message.from_user.id, "cancel", "Отмена действия через /cancel")
    cancel_msg = await message.answer("❌ Действие отменено")
    asyncio.create_task(delete_message_safe(cancel_msg, 3))
    asyncio.create_task(delete_message_safe(message, 3))
    logger.info(f"Админ {message.from_user.id} отменил действие")


@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    """Открытие админ-панели"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    await state.clear()
    await log_admin_action(message.from_user.id, "open_admin", "Открытие админ-панели")
    
    try:
        await message.answer(
            "⚙️ <b>Админ-панель</b>\n\nВыбери действие:",
            parse_mode="HTML",
            reply_markup=await get_admin_keyboard(message.from_user.id)
        )
        logger.info(f"Админ {message.from_user.id} открыл админ-панель")
    except Exception as e:
        logger.error(f"Ошибка открытия админ-панели: {e}")
        await send_temp_message(message, "❌ Ошибка загрузки админ-панели")


@router.message(Command("stats"))
async def stats_command(message: types.Message):
    """Показ статистики"""
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Только супер-админ")
        return
    
    await log_admin_action(message.from_user.id, "view_stats", "Просмотр статистики")
    
    stats = await get_stats()
    if not stats:
        await send_temp_message(message, "❌ Ошибка получения статистики")
        return
    
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"📦 Заказов: {stats.get('total_orders', 0)}\n"
        f"💰 Оборот: {stats.get('total_amount', 0)}₽\n"
        f"👥 Пользователей: {stats.get('total_users', 0)}\n"
        f"🕐 {datetime.now().strftime('%H:%M:%S')}",
        parse_mode="HTML"
    )
    logger.info(f"Админ {message.from_user.id} просмотрел статистику")


@router.message(Command("gallery"))
async def show_gallery(message: types.Message):
    """Показ галереи"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    try:
        photos = await get_gallery_photos(limit=10)
        if not photos:
            await send_temp_message(message, "📸 Галерея пуста")
            return
        
        await log_admin_action(message.from_user.id, "view_gallery", "Просмотр галереи")
        
        media_group = []
        for pid, caption, date in photos[:10]:
            media_group.append(
                InputMediaPhoto(
                    media=pid,
                    caption=f"📅 {date}\n{caption or 'без подписи'}",
                    parse_mode="HTML"
                )
            )
        
        if media_group:
            await message.answer_media_group(media_group)
            logger.info(f"Админ {message.from_user.id} просмотрел галерею ({len(photos)} фото)")
    except Exception as e:
        logger.error(f"Ошибка показа галереи: {e}")
        await send_temp_message(message, "❌ Ошибка загрузки галереи")


# ========== ОБРАБОТКА КНОПОК АДМИНКИ ==========
@router.callback_query(F.data.startswith("admin_"))
async def admin_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка кнопок админ-панели"""
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return
    
    parts = callback.data.split("_", 1)
    if len(parts) < 2:
        await callback.answer("❌ Неверный формат")
        return
    
    action = parts[1]
    
    # Проверка активного состояния
    current_state = await state.get_state()
    if current_state and action not in ("cancel", "post_cancel"):
        await callback.answer("❌ Завершите текущее действие (/cancel)", show_alert=True)
        return
    
    await callback.answer()
    
    try:
        if action == "orders":
            txns = await get_all_transactions(limit=20)
            if not txns:
                await callback.message.answer("📦 Заказов пока нет")
                return
            
            text = "📦 <b>Последние заказы:</b>\n\n"
            for t in txns[:10]:
                text += f"💰 {t.get('amount', 0)}₽ | {t.get('gift_name', 'N/A')} | @{t.get('username', 'нет')}\n"
            await callback.message.answer(text, parse_mode="HTML")
            await log_admin_action(user_id, "view_orders", "Просмотр заказов")
            logger.info(f"Админ {user_id} просмотрел заказы")
        
        elif action == "stats":
            if user_id != SUPER_ADMIN_ID:
                await callback.answer("❌ Только супер-админ", show_alert=True)
                return
            
            stats = await get_stats()
            if not stats:
                await callback.message.answer("❌ Ошибка получения статистики")
                return
            
            await callback.message.answer(
                f"📊 <b>Статистика</b>\n\n"
                f"📦 Заказов: {stats.get('total_orders', 0)}\n"
                f"💰 Оборот: {stats.get('total_amount', 0)}₽\n"
                f"👥 Пользователей: {stats.get('total_users', 0)}",
                parse_mode="HTML"
            )
            await log_admin_action(user_id, "view_stats", "Просмотр статистики из меню")
        
        elif action == "gallery":
            await callback.message.answer(
                "📸 <b>Галерея</b>\n\n"
                "Отправь фото с подписью — добавлю в галерею.\n"
                "Пример: фото + подпись 'Красивое фото со стрима'\n\n"
                "❌ Отмена: /cancel",
                parse_mode="HTML"
            )
            logger.info(f"Админ {user_id} начал добавление в галерею")
        
        elif action == "add_gift":
            if user_id not in (SUPER_ADMIN_ID, SUPPORT_ADMIN_ID):
                await callback.answer("❌ Только админы с правами на подарки", show_alert=True)
                return
            
            await state.clear()
            await state.set_state(AdminStates.adding_gift)
            
            await callback.message.answer(
                "🎁 <b>Добавление подарка</b>\n\n"
                "Формат: <code>Название | Цена | Описание | Иконка</code>\n"
                "Пример: <code>🍕 Пицца | 500 | Вкусная пицца | 🍕</code>\n\n"
                "⏰ Время: 30 минут\n"
                "❌ Отмена: /cancel",
                parse_mode="HTML"
            )
            await log_admin_action(user_id, "start_add_gift", "Начало добавления подарка")
            logger.info(f"Админ {user_id} начал добавление подарка")
        
        elif action == "create_post":
            await state.clear()
            await state.set_state(AdminStates.creating_post_text)
            
            await callback.message.answer(
                "📢 <b>Создание поста — Шаг 1/4</b>\n\n"
                "✏️ Напиши текст поста\n\n"
                "⏰ Время: 30 минут\n"
                "❌ Отмена: /cancel",
                parse_mode="HTML"
            )
            await log_admin_action(user_id, "start_create_post", "Начало создания поста")
            logger.info(f"Админ {user_id} начал создание поста")
    
    except Exception as e:
        logger.error(f"Ошибка обработки кнопки: {e}")
        await send_temp_message(callback.message, f"❌ Ошибка: {e}")


# ========== ДОБАВЛЕНИЕ ПОДАРКА ==========
@router.message(AdminStates.adding_gift)
async def handle_add_gift(message: types.Message, state: FSMContext):
    """Обработка добавления подарка"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await state.clear()
        return
    
    if not message.text:
        await send_temp_message(message, "❌ Ожидаю текст в формате: Название | Цена | Описание | Иконка")
        return
    
    try:
        parts = message.text.split("|")
        if len(parts) < 3:
            await send_temp_message(
                message,
                "❌ Ошибка. Нужно: <code>Название | Цена | Описание | Иконка</code>",
                parse_mode="HTML"
            )
            return
        
        name = parts[0].strip()
        
        try:
            price = int(parts[1].strip())
            if price <= 0:
                raise ValueError("Цена должна быть положительной")
        except ValueError as e:
            await send_temp_message(message, f"❌ Неверная цена: {e}")
            return
        
        desc = parts[2].strip()
        icon = parts[3].strip() if len(parts) > 3 else "🎁"
        
        success = await add_gift(name, price, desc, icon)
        
        if success:
            await message.answer(f"✅ Подарок <b>{name}</b> добавлен!", parse_mode="HTML")
            await log_admin_action(user_id, "add_gift", f"Добавлен подарок: {name} ({price}₽)")
            logger.info(f"Админ {user_id} добавил подарок: {name}")
        else:
            await send_temp_message(message, "❌ Ошибка при добавлении подарка в БД")
            
    except Exception as e:
        logger.error(f"Ошибка добавления подарка: {e}")
        await send_temp_message(message, f"❌ Ошибка: {type(e).__name__}")
    finally:
        await state.clear()


# ========== СОЗДАНИЕ ПОСТА ==========
@router.message(AdminStates.creating_post_text)
async def handle_post_text(message: types.Message, state: FSMContext):
    """Обработка текста поста"""
    user_id = message.from_user.id
    
    if not message.text or len(message.text) < 10:
        await send_temp_message(message, "❌ Текст слишком короткий (минимум 10 символов)")
        return
    
    if len(message.text) > 4000:
        await send_temp_message(message, "❌ Текст слишком длинный (максимум 4000 символов)")
        return
    
    await state.update_data(post_text=message.text)
    await state.set_state(AdminStates.creating_post_photo)
    
    await message.answer(
        "📢 <b>Создание поста — Шаг 2/4</b>\n\n"
        "📸 Отправь фото или /skip для пропуска\n\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )
    logger.info(f"Админ {user_id} ввёл текст поста")


@router.message(Command("skip"), AdminStates.creating_post_photo)
async def skip_photo(message: types.Message, state: FSMContext):
    """Пропуск фото"""
    user_id = message.from_user.id
    
    await state.update_data(post_photo_id=None)
    await state.set_state(AdminStates.creating_post_preview)
    
    data = await state.get_data()
    await show_preview(message, data.get("post_text", ""), None, state)
    logger.info(f"Админ {user_id} пропустил фото для поста")


@router.message(F.photo, AdminStates.creating_post_photo)
async def handle_post_photo(message: types.Message, state: FSMContext):
    """Обработка фото для поста"""
    user_id = message.from_user.id
    
    photo = message.photo[-1]
    await state.update_data(post_photo_id=photo.file_id)
    await state.set_state(AdminStates.creating_post_preview)
    
    data = await state.get_data()
    await show_preview(message, data.get("post_text", ""), photo.file_id, state)
    logger.info(f"Админ {user_id} добавил фото к посту")


async def show_preview(message: types.Message, text: str, photo_id: Optional[str], state: FSMContext):
    """Показ предпросмотра поста"""
    preview_text = text[:MAX_PREVIEW_LENGTH]
    if len(text) > MAX_PREVIEW_LENGTH:
        preview_text += f"\n\n... (ещё {len(text) - MAX_PREVIEW_LENGTH} символов)"
    
    preview_msg = f"📢 <b>Предпросмотр поста:</b>\n\n{preview_text}"
    
    if photo_id:
        await message.answer_photo(photo_id, caption=preview_msg, parse_mode="HTML")
    else:
        await message.answer(preview_msg, parse_mode="HTML")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="post_publish")],
        [InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="post_edit_text")],
        [InlineKeyboardButton(text="📸 Изменить фото", callback_data="post_edit_photo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="post_cancel")]
    ])
    await message.answer("Что делаем дальше?", reply_markup=kb)


# ========== ПУБЛИКАЦИЯ ПОСТА ==========
@router.callback_query(F.data == "post_publish", AdminStates.creating_post_preview)
async def publish_post(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение публикации поста"""
    if not validate_channel_id(CHANNEL_ID):
        await callback.answer("❌ Канал не настроен", show_alert=True)
        await callback.message.answer(
            "❌ CHANNEL_ID не настроен корректно. Должен начинаться с -100",
            parse_mode="HTML"
        )
        return
    
    has_perms = await check_bot_channel_permissions(CHANNEL_ID)
    if not has_perms:
        await callback.answer("❌ Нет прав в канале", show_alert=True)
        await callback.message.answer(
            "❌ У бота нет прав администратора в канале\n"
            f"Канал: <code>{CHANNEL_ID}</code>",
            parse_mode="HTML"
        )
        return
    
    await callback.message.answer(
        "⚠️ <b>Подтверждение публикации</b>\n\n"
        "Пост будет опубликован в канале.\n"
        "Нажмите ещё раз для подтверждения.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, опубликовать", callback_data="post_publish_confirm")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="post_edit_text")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "post_publish_confirm", AdminStates.creating_post_preview)
async def publish_post_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Финальная публикация поста"""
    user_id = callback.from_user.id
    
    data = await state.get_data()
    text = data.get("post_text", "")
    photo_id = data.get("post_photo_id")
    
    if not text:
        await callback.answer("❌ Нет текста", show_alert=True)
        await state.clear()
        return
    
    bot = get_bot()
    bot_username = (await bot.get_me()).username or "GiftFlowDB_bot"
    
    post_text = (
        f"{text}\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📺 <b>Twitch</b>: {TWITCH_URL}\n"
        f"📷 <b>Instagram</b>: {INSTAGRAM_URL}\n"
        f"🎁 <b>Подарки</b>: @{bot_username}"
    )
    
    try:
        if photo_id:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo_id,
                caption=post_text,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=post_text,
                parse_mode="HTML"
            )
        
        await callback.message.answer("✅ Пост опубликован в канале!")
        await log_admin_action(user_id, "publish_post", f"Опубликован пост ({len(text)} символов)")
        logger.info(f"Админ {user_id} опубликовал пост")
        await state.clear()
        
    except TelegramBadRequest as e:
        logger.error(f"Ошибка публикации: {e}")
        await callback.message.answer(f"❌ Ошибка: {str(e)[:200]}")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        await callback.message.answer("❌ Непредвиденная ошибка")
        await state.clear()
    
    await callback.answer()


# ========== РЕДАКТИРОВАНИЕ ПОСТА ==========
@router.callback_query(F.data == "post_edit_text", AdminStates.creating_post_preview)
async def edit_post_text(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование текста поста"""
    await state.set_state(AdminStates.editing_post_text)
    await callback.message.answer(
        "✏️ <b>Редактирование текста</b>\n\n"
        "Отправь новый текст поста\n\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()
    logger.info(f"Админ {callback.from_user.id} редактирует текст")


@router.message(AdminStates.editing_post_text)
async def handle_edit_post_text(message: types.Message, state: FSMContext):
    """Обработка отредактированного текста"""
    if not message.text or len(message.text) < 10:
        await send_temp_message(message, "❌ Текст слишком короткий")
        return
    
    await state.update_data(post_text=message.text)
    await state.set_state(AdminStates.creating_post_preview)
    
    data = await state.get_data()
    await show_preview(message, data.get("post_text", ""), data.get("post_photo_id"), state)
    logger.info(f"Админ {message.from_user.id} обновил текст")


@router.callback_query(F.data == "post_edit_photo", AdminStates.creating_post_preview)
async def edit_post_photo(callback: types.CallbackQuery, state: FSMContext):
    """Редактирование фото поста"""
    await state.set_state(AdminStates.creating_post_photo)
    await callback.message.answer(
        "📸 <b>Изменение фото</b>\n\n"
        "Отправь новое фото или /skip для удаления\n\n"
        "❌ Отмена: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()
    logger.info(f"Админ {callback.from_user.id} редактирует фото")


@router.callback_query(F.data == "post_cancel", AdminStates.creating_post_preview)
async def cancel_post_button(callback: types.CallbackQuery, state: FSMContext):
    """Отмена создания поста"""
    await state.clear()
    await log_admin_action(callback.from_user.id, "cancel_post", "Отмена создания поста")
    cancel_msg = await callback.message.answer("❌ Создание поста отменено")
    asyncio.create_task(delete_message_safe(cancel_msg, 3))
    await callback.answer()
    logger.info(f"Админ {callback.from_user.id} отменил создание поста")


# ========== ГАЛЕРЕЯ ==========
@router.message(F.photo)
async def handle_gallery_photo(message: types.Message, state: FSMContext):
    """Обработка фото для галереи"""
    user_id = message.from_user.id
    
    if user_id not in ADMIN_IDS:
        return
    
    current_state = await state.get_state()
    
    # Если это фото для поста — игнорируем, оно обрабатывается в другом хендлере
    if current_state in (AdminStates.creating_post_photo, AdminStates.creating_post_preview, AdminStates.editing_post_photo):
        return
    
    if current_state == AdminStates.adding_gift:
        await send_temp_message(message, "❌ Сейчас ожидается текст для подарка")
        return
    
    # Сохраняем в галерею
    try:
        photo = message.photo[-1]
        await add_gallery_photo(photo.file_id, message.caption or "", user_id)
        success_msg = await message.answer("✅ Фото добавлено в галерею!")
        asyncio.create_task(delete_message_safe(success_msg, 5))
        await log_admin_action(user_id, "add_gallery_photo", "Добавление фото в галерею")
        logger.info(f"Админ {user_id} добавил фото в галерею")
    except Exception as e:
        logger.error(f"Ошибка сохранения фото: {e}")
        error_msg = await message.answer(f"❌ Ошибка: {e}")
        asyncio.create_task(delete_message_safe(error_msg, 5))


# ========== HEALTH CHECK ==========
@router.message(Command("health"))
async def health_check(message: types.Message):
    """Проверка состояния бота"""
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Только супер-админ")
        return
    
    checks = {
        "🤖 Бот": "✅ Работает",
        "📊 Статистика": "⏳ Проверка...",
        "📺 Канал": "⏳ Проверка...",
        "💾 База данных": "⏳ Проверка..."
    }
    
    status_msg = await message.answer("🔍 <b>Проверка состояния...</b>", parse_mode="HTML")
    
    # Проверка статистики
    try:
        stats = await get_stats()
        checks["📊 Статистика"] = "✅ OK" if stats else "❌ Ошибка"
    except Exception as e:
        checks["📊 Статистика"] = f"❌ {type(e).__name__}"
    
    # Проверка канала
    if validate_channel_id(CHANNEL_ID):
        has_perms = await check_bot_channel_permissions(CHANNEL_ID)
        checks["📺 Канал"] = "✅ OK" if has_perms else "❌ Нет прав"
    else:
        checks["📺 Канал"] = "❌ Не настроен"
    
    # Проверка БД
    try:
        await get_stats()
        checks["💾 База данных"] = "✅ OK"
    except Exception as e:
        checks["💾 База данных"] = f"❌ {type(e).__name__}"
    
    report = "🏥 <b>Health Check</b>\n\n"
    for check, status in checks.items():
        report += f"{check}: {status}\n"
    
    report += f"\n🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await status_msg.edit_text(report, parse_mode="HTML")
    await log_admin_action(message.from_user.id, "health_check", "Проверка состояния бота")
    logger.info(f"Админ {message.from_user.id} выполнил health check")
