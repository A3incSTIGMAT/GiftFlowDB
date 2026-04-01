import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import get_main_menu_keyboard, get_back_keyboard, get_admin_keyboard, get_super_admin_choice_keyboard
from database import get_user, add_user
from config import ADMIN_IDS, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID, STREAMER_NAME

logger = logging.getLogger(__name__)
router = Router()

# Хранилище режима для супер-админа
super_admin_mode = {}


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    try:
        user_id = message.from_user.id
        
        user = await get_user(user_id)
        if not user:
            await add_user(user_id, message.from_user.username, message.from_user.first_name)
            logger.info(f"✅ Новый пользователь: {user_id}")
        
        # Супер-админ — показываем выбор режима
        if user_id == SUPER_ADMIN_ID:
            super_admin_mode[user_id] = None
            await message.answer(
                f"👑 <b>Привет, Супер-админ!</b>\n\n"
                f"Выбери режим работы:\n\n"
                f"👤 <b>Режим пользователя</b> — видишь бота как обычный зритель\n"
                f"⚙️ <b>Админ-панель</b> — управление ботом, статистика, галерея",
                parse_mode="HTML",
                reply_markup=await get_super_admin_choice_keyboard()
            )
        # Лана — сразу в админ-панель
        elif user_id == SUPPORT_ADMIN_ID:
            await message.answer(
                f"👋 <b>Привет, {STREAMER_NAME}!</b>\n\n"
                f"Управление ботом:\n\n"
                f"📢 <b>Создать пост</b> — кнопка в админ-панели\n"
                f"📦 <b>Заказы</b> — список ожидающих платежей\n"
                f"📸 <b>Галерея</b> — фото для постов",
                parse_mode="HTML",
                reply_markup=await get_admin_keyboard(user_id)
            )
        # Обычный пользователь
        else:
            await message.answer(
                f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
                f"🎮 Это бот стримерши <b>{STREAMER_NAME}</b>\n\n"
                f"• Подписывайся на соцсети\n"
                f"• Дари подарки — они появятся на стриме\n"
                f"• Вопросы — пиши менеджеру",
                parse_mode="HTML",
                reply_markup=await get_main_menu_keyboard()
            )
    except Exception as e:
        logger.error(f"❌ Ошибка в /start: {e}")


@router.message(Command("user"))
async def cmd_user(message: types.Message):
    """Переключение в режим пользователя (только для супер-админа)"""
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Доступ запрещён")
        return
    super_admin_mode[message.from_user.id] = "user"
    await message.answer(
        "👤 <b>Режим пользователя</b>\n\n"
        "Теперь ты видишь бота как обычный зритель.\n"
        "Чтобы вернуться в админ-панель, используй /admin",
        parse_mode="HTML",
        reply_markup=await get_main_menu_keyboard()
    )


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Переключение в админ-панель"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выбери раздел управления:",
        parse_mode="HTML",
        reply_markup=await get_admin_keyboard(message.from_user.id)
    )


@router.callback_query(F.data == "mode_user")
async def mode_user(callback: types.CallbackQuery):
    if callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("❌ Доступ запрещён")
        return
    super_admin_mode[callback.from_user.id] = "user"
    await callback.message.edit_text(
        "👤 <b>Режим пользователя</b>",
        parse_mode="HTML",
        reply_markup=await get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "mode_admin")
async def mode_admin(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>",
        parse_mode="HTML",
        reply_markup=await get_admin_keyboard(callback.from_user.id)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        if user_id == SUPER_ADMIN_ID:
            if super_admin_mode.get(user_id) == "user":
                await callback.message.edit_text(
                    "👋 <b>Главное меню</b>",
                    parse_mode="HTML",
                    reply_markup=await get_main_menu_keyboard()
                )
            else:
                await callback.message.edit_text(
                    "👑 <b>Супер-админ!</b>\n\nВыбери режим работы:",
                    parse_mode="HTML",
                    reply_markup=await get_super_admin_choice_keyboard()
                )
        elif user_id in ADMIN_IDS:
            await callback.message.edit_text(
                "⚙️ <b>Админ-панель</b>",
                parse_mode="HTML",
                reply_markup=await get_admin_keyboard(user_id)
            )
        else:
            await callback.message.edit_text(
                "👋 <b>Главное меню</b>",
                parse_mode="HTML",
                reply_markup=await get_main_menu_keyboard()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в back_to_main: {e}")


@router.callback_query(F.data == "contact_support")
async def contact_support(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text(
            "💬 <b>Связь с менеджером</b>\n\n"
            "Просто напиши сюда свой вопрос — менеджер ответит в ближайшее время.",
            parse_mode="HTML",
            reply_markup=await get_back_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в contact_support: {e}")


@router.message(Command("test"))
async def cmd_test(message: types.Message):
    await message.answer(
        "✅ <b>Бот работает!</b>\n\n"
        f"🆔 Твой ID: <code>{message.from_user.id}</code>",
        parse_mode="HTML"
    )


# ========== ВРЕМЕННЫЙ ХЕНДЛЕР ДЛЯ ПОЛУЧЕНИЯ ID КАНАЛА ==========
@router.message(Command("channel_id"))
async def get_channel_id(message: types.Message):
    """Получение ID канала (временный хендлер)"""
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        chat_title = message.forward_from_chat.title or "без названия"
        chat_type = "канал" if message.forward_from_chat.type == "channel" else "чат"
        await message.answer(
            f"✅ <b>Информация о {chat_type}</b>\n\n"
            f"📢 Название: {chat_title}\n"
            f"🆔 ID: <code>{chat_id}</code>\n\n"
            f"📝 Скопируй этот ID и добавь в переменную CHANNEL_ID в Amvera\n\n"
            f"💡 Пример: <code>CHANNEL_ID={chat_id}</code>",
            parse_mode="HTML"
        )
        logger.info(f"Пользователь {message.from_user.id} получил ID канала: {chat_id}")
    else:
        await message.answer(
            "📎 <b>Как получить ID канала:</b>\n\n"
            "1️⃣ Перешли любое сообщение из канала в этот чат\n"
            "2️⃣ Затем снова напиши /channel_id\n\n"
            "🔹 Канал: @lanatwitchh\n\n"
            "📌 Если у тебя нет сообщений из канала, просто перешли любое сообщение сюда.",
            parse_mode="HTML"
        )
