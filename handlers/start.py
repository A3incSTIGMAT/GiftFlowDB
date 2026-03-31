import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from keyboards import get_main_menu_keyboard, get_back_keyboard, get_admin_keyboard, get_super_admin_choice_keyboard
from database import get_user, add_user
from config import ADMIN_IDS, SUPER_ADMIN_ID, STREAMER_NAME

logger = logging.getLogger(__name__)
router = Router()

# Хранилище режима для супер-админа (чтобы помнить, в каком режиме он находится)
super_admin_mode = {}


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    try:
        user = await get_user(message.from_user.id)
        if not user:
            await add_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
            logger.info(f"Новый пользователь: {message.from_user.id}")
        else:
            logger.info(f"Существующий пользователь: {message.from_user.id}")
        
        # Супер-админ — показываем выбор режима
        if message.from_user.id == SUPER_ADMIN_ID:
            # Сбрасываем режим при новом старте
            super_admin_mode[message.from_user.id] = None
            
            await message.answer(
                f"👑 <b>Привет, Супер-админ {message.from_user.first_name}!</b>\n\n"
                f"Выбери режим работы:\n\n"
                f"👤 <b>Режим пользователя</b> — видишь бота как обычный зритель\n"
                f"⚙️ <b>Админ-панель</b> — управление ботом, статистика, галерея\n\n"
                f"💡 <b>Подсказка:</b> Используй команды /user или /admin для быстрого переключения",
                parse_mode="HTML",
                reply_markup=await get_super_admin_choice_keyboard()
            )
        
        # Обычный админ (Лана) — сразу в админ-панель
        elif message.from_user.id in ADMIN_IDS:
            await message.answer(
                f"👋 <b>Привет, Админ!</b>\n\n"
                f"Управление ботом {STREAMER_NAME}",
                parse_mode="HTML",
                reply_markup=await get_admin_keyboard(message.from_user.id)
            )
        
        # Обычный пользователь
        else:
            await message.answer(
                f"👋 <b>Привет, {message.from_user.first_name}!</b>\n\n"
                f"🎮 Это бот стримерши <b>{STREAMER_NAME}</b>\n\n"
                f"• Подписывайся на соцсети\n"
                f"• Дари подарки — они появятся на стриме\n"
                f"• Вопросы — пиши менеджеру\n\n"
                f"👇 Выбери действие:",
                parse_mode="HTML",
                reply_markup=await get_main_menu_keyboard()
            )
            
        logger.info(f"Команда /start выполнена для {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка в /start: {e}")
        await message.answer(
            "❌ Произошла ошибка. Попробуй позже.",
            parse_mode="HTML"
        )


@router.message(Command("user"))
async def cmd_user(message: types.Message):
    """Переключение в режим пользователя (только для супер-админа)"""
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Доступ запрещён")
        return
    
    super_admin_mode[message.from_user.id] = "user"
    
    await message.answer(
        f"👤 <b>Режим пользователя</b>\n\n"
        f"Теперь ты видишь бота как обычный зритель.\n"
        f"Чтобы вернуться в админ-панель, используй /admin",
        parse_mode="HTML",
        reply_markup=await get_main_menu_keyboard()
    )


@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Переключение в админ-панель"""
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    if message.from_user.id == SUPER_ADMIN_ID:
        super_admin_mode[message.from_user.id] = "admin"
    
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выбери раздел управления:",
        parse_mode="HTML",
        reply_markup=await get_admin_keyboard(message.from_user.id)
    )


@router.callback_query(F.data == "mode_user")
async def mode_user(callback: types.CallbackQuery):
    """Переключение в режим пользователя (через кнопку)"""
    if callback.from_user.id != SUPER_ADMIN_ID:
        await callback.answer("❌ Доступ запрещён")
        return
    
    super_admin_mode[callback.from_user.id] = "user"
    
    await callback.message.edit_text(
        f"👤 <b>Режим пользователя</b>\n\n"
        f"Теперь ты видишь бота как обычный зритель.\n"
        f"Чтобы вернуться в админ-панель, используй /admin или нажми кнопку ниже.",
        parse_mode="HTML",
        reply_markup=await get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "mode_admin")
async def mode_admin(callback: types.CallbackQuery):
    """Переключение в режим админа (через кнопку)"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Доступ запрещён")
        return
    
    if callback.from_user.id == SUPER_ADMIN_ID:
        super_admin_mode[callback.from_user.id] = "admin"
    
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выбери раздел управления:",
        parse_mode="HTML",
        reply_markup=await get_admin_keyboard(callback.from_user.id)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    """Возврат в главное меню (в зависимости от режима)"""
    try:
        current_text = callback.message.text or ""
        
        # Супер-админ — показываем меню выбора режима
        if callback.from_user.id == SUPER_ADMIN_ID:
            # Если супер-админ в режиме пользователя — показываем главное меню
            if super_admin_mode.get(callback.from_user.id) == "user":
                if "Главное меню" in current_text or "Выбери действие" in current_text:
                    await callback.answer("🔹 Вы уже в главном меню")
                    return
                
                await callback.message.edit_text(
                    "👋 <b>Главное меню</b>",
                    parse_mode="HTML",
                    reply_markup=await get_main_menu_keyboard()
                )
            else:
                # Показываем выбор режима
                if "Выбери режим" in current_text:
                    await callback.answer("🔹 Вы уже в меню выбора")
                    return
                
                await callback.message.edit_text(
                    f"👑 <b>Супер-админ!</b>\n\n"
                    f"Выбери режим работы:\n\n"
                    f"👤 <b>Режим пользователя</b> — видишь бота как обычный зритель\n"
                    f"⚙️ <b>Админ-панель</b> — управление ботом, статистика, галерея",
                    parse_mode="HTML",
                    reply_markup=await get_super_admin_choice_keyboard()
                )
        
        # Обычный админ (Лана)
        elif callback.from_user.id in ADMIN_IDS:
            if "Админ-панель" in current_text:
                await callback.answer("🔹 Вы уже в админ-панели")
                return
            
            await callback.message.edit_text(
                "⚙️ <b>Админ-панель</b>",
                parse_mode="HTML",
                reply_markup=await get_admin_keyboard(callback.from_user.id)
            )
        
        # Обычный пользователь
        else:
            if "Главное меню" in current_text or "Выбери действие" in current_text:
                await callback.answer("🔹 Вы уже в главном меню")
                return
            
            await callback.message.edit_text(
                "👋 <b>Главное меню</b>",
                parse_mode="HTML",
                reply_markup=await get_main_menu_keyboard()
            )
        
        await callback.answer()
        
    except Exception as e:
        error_str = str(e)
        if "message is not modified" in error_str:
            await callback.answer("🔹 Вы уже здесь")
        else:
            logger.error(f"Ошибка в back_to_main: {e}")


@router.callback_query(F.data == "contact_support")
async def contact_support(callback: types.CallbackQuery):
    """Связь с поддержкой"""
    try:
        current_text = callback.message.text or ""
        
        if "Связь с менеджером" in current_text:
            await callback.answer("🔹 Вы уже в разделе поддержки")
            return
        
        await callback.message.edit_text(
            "💬 <b>Связь с менеджером</b>\n\n"
            "Просто напиши сюда свой вопрос — менеджер ответит в ближайшее время.",
            parse_mode="HTML",
            reply_markup=await get_back_keyboard()
        )
        await callback.answer()
        
    except Exception as e:
        error_str = str(e)
        if "message is not modified" in error_str:
            await callback.answer("🔹 Вы уже в разделе поддержки")
        else:
            logger.error(f"Ошибка в contact_support: {e}")


@router.message(Command("test"))
async def cmd_test(message: types.Message):
    """Тестовая команда"""
    await message.answer(
        "✅ <b>Бот работает!</b>\n\n"
        f"🆔 Твой ID: <code>{message.from_user.id}</code>\n\n"
        f"📊 <b>Твой статус:</b>\n"
        f"{'👑 Супер-админ' if message.from_user.id == SUPER_ADMIN_ID else '👤 Админ' if message.from_user.id in ADMIN_IDS else '👤 Пользователь'}",
        parse_mode="HTML"
    )
