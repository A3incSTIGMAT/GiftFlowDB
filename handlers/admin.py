from aiogram import Router, types, F
from aiogram.filters import Command
from config import ADMIN_IDS, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID
from database import get_all_transactions, add_gallery_photo, get_gallery_photos
from keyboards import get_admin_keyboard

router = Router()

async def get_admin_keyboard(user_id: int):
    from keyboards import get_admin_keyboard as kb
    return await kb(user_id)

@router.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выбери раздел:",
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
        transactions = await get_all_transactions()
        if not transactions:
            await callback.message.answer("📦 Заказов пока нет")
            return
        
        text = "📦 <b>Последние заказы:</b>\n\n"
        for t in transactions[:10]:
            text += f"💰 {t['amount']}₽ | {t['gift_name']} | @{t.get('username', 'нет')}\n"
        await callback.message.answer(text, parse_mode="HTML")
    
    elif action == "stats" and callback.from_user.id == SUPER_ADMIN_ID:
        transactions = await get_all_transactions()
        total = sum(t['amount'] for t in transactions)
        await callback.message.answer(
            f"📊 <b>Статистика</b>\n\n"
            f"📦 Заказов: {len(transactions)}\n"
            f"💰 Оборот: {total}₽",
            parse_mode="HTML"
        )
    
    elif action == "gallery":
        await callback.message.answer(
            "📸 <b>Галерея фото</b>\n\n"
            "Отправь мне фото с подписью в одном сообщении — я добавлю его в галерею.\n\n"
            "Пример: фото + подпись 'Красивое фото со стрима'",
            parse_mode="HTML"
        )
    
    await callback.answer()

@router.message(F.photo)
async def handle_gallery_photo(message: types.Message):
    if message.from_user.id != SUPPORT_ADMIN_ID:
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
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Доступ запрещён")
        return
    
    photos = await get_gallery_photos()
    if not photos:
        await message.answer("📸 Галерея пуста. Загрузи фото через админ-панель.")
        return
    
    for photo_id, caption in photos[:5]:
        await message.answer_photo(
            photo_id,
            caption=caption if caption else "Фото из галереи",
            parse_mode="HTML"
        )
