from aiogram import Router, types, F
from aiogram.filters import Command
from config import ADMIN_IDS, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID
from database import get_all_transactions
from keyboards import get_admin_keyboard

router = Router()

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
        for t in transactions[-10:]:
            text += f"💰 {t['amount']}₽ | {t['gift_name']} | @{t.get('username', 'нет')}\n"
        await callback.message.answer(text, parse_mode="HTML")
    
    elif action == "stats" and callback.from_user.id == SUPER_ADMIN_ID:
        # Полная статистика (только для супер-админа)
        transactions = await get_all_transactions()
        total = sum(t['amount'] for t in transactions)
        await callback.message.answer(
            f"📊 <b>Статистика</b>\n\n"
            f"📦 Заказов: {len(transactions)}\n"
            f"💰 Оборот: {total}₽",
            parse_mode="HTML"
        )
    
    elif action == "gallery" and callback.from_user.id == SUPPORT_ADMIN_ID:
        await callback.message.answer(
            "📸 <b>Загрузи фото для поста</b>\n\n"
            "Просто отправь мне фото с подписью в одном сообщении",
            parse_mode="HTML"
        )
    
    await callback.answer()
