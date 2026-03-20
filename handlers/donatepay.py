import aiohttp
import logging
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import DONATEPAY_API_KEY, DONATEPAY_WALLET_ID, SUPER_ADMIN_ID, SUPPORT_ADMIN_ID

logger = logging.getLogger(__name__)

# Создаём роутер для обработки вебхуков от DonatePay
router = Router()


async def create_donatepay_invoice(amount: int, description: str, user_id: int) -> str:
    """Создаёт счёт в DonatePay и возвращает ссылку на оплату"""
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                "https://donatepay.ru/api/v1/invoice/create",
                headers={"Authorization": f"Bearer {DONATEPAY_API_KEY}"},
                json={
                    "amount": amount,
                    "currency": "RUB",
                    "description": description,
                    "user_id": user_id,
                    "wallet_id": DONATEPAY_WALLET_ID
                }
            )
            
            if response.status == 200:
                data = await response.json()
                logger.info(f"✅ Invoice created: {data}")
                return data.get("payment_url")
            else:
                logger.error(f"DonatePay error: {response.status} - {await response.text()}")
                return None
    except Exception as e:
        logger.error(f"DonatePay exception: {e}")
        return None


async def check_donatepay_invoice(invoice_id: str) -> dict:
    """Проверяет статус счёта в DonatePay"""
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.get(
                f"https://donatepay.ru/api/v1/invoice/info",
                headers={"Authorization": f"Bearer {DONATEPAY_API_KEY}"},
                params={"invoice_id": invoice_id}
            )
            
            if response.status == 200:
                data = await response.json()
                return data
            else:
                logger.error(f"DonatePay check error: {response.status}")
                return None
    except Exception as e:
        logger.error(f"DonatePay check exception: {e}")
        return None


@router.message(lambda message: message.text and "donatepay" in message.text.lower())
async def handle_donatepay_message(message: types.Message):
    """Обработка сообщений с донатами (для админов)"""
    if message.from_user.id not in [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]:
        return
    
    await message.answer(
        "💰 <b>DonatePay интеграция активна</b>\n\n"
        "Все донаты обрабатываются автоматически.\n"
        "При получении доната бот сам вручит подарок.",
        parse_mode="HTML"
    )


# ==================== ВЕБХУК ДЛЯ DONATEPAY (если понадобится) ====================

async def webhook_handler(request_data: dict):
    """Обработка вебхуков от DonatePay (если настроить)"""
    try:
        # Проверяем подпись (если есть)
        # signature = request_data.get('signature')
        
        invoice_id = request_data.get('invoice_id')
        amount = request_data.get('amount')
        status = request_data.get('status')
        user_id = request_data.get('user_id')
        description = request_data.get('description')
        
        if status == 'paid':
            logger.info(f"💰 Получен донат: {amount}₽ от user_{user_id} за {description}")
            
            # Здесь можно отправить уведомление админам
            # await bot.send_message(SUPPORT_ADMIN_ID, f"💰 Новый донат! {amount}₽")
            
            return {"status": "ok", "message": "DONATION_RECEIVED"}
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}
