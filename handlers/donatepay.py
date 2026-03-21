import aiohttp
import logging
from aiogram import Router

logger = logging.getLogger(__name__)

router = Router()


async def create_donatepay_invoice(amount: int, description: str, user_id: int) -> str:
    """Создаёт счёт в DonatePay и возвращает ссылку на оплату"""
    try:
        # Импортируем здесь, чтобы избежать циклических импортов
        from config import DONATEPAY_API_KEY, DONATEPAY_WALLET_ID
        
        if not DONATEPAY_API_KEY:
            logger.error("DONATEPAY_API_KEY не настроен!")
            return None
        
        if not DONATEPAY_WALLET_ID:
            logger.error("DONATEPAY_WALLET_ID не настроен!")
            return None
        
        logger.info(f"Создаём счёт: {amount}₽ за {description} для user_{user_id}")
        
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
            
            logger.info(f"DonatePay ответ: {response.status}")
            
            if response.status == 200:
                data = await response.json()
                logger.info(f"✅ Invoice created: {data}")
                return data.get("payment_url")
            else:
                error_text = await response.text()
                logger.error(f"DonatePay error {response.status}: {error_text}")
                return None
                
    except Exception as e:
        logger.error(f"DonatePay exception: {e}")
        return None
