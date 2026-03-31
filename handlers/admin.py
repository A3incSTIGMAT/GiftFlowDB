import logging
from aiogram import Router, types, F

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "admin_create_post")
async def test_create_post(callback: types.CallbackQuery):
    await callback.answer("✅ Кнопка работает! Теперь можно писать логику.", show_alert=True)
    logger.info(f"🔥 Создать пост нажал {callback.from_user.id}")
