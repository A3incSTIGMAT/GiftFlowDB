import aiohttp
import logging
from aiogram import Router
from config import DONATEPAY_API_KEY, DONATEPAY_WALLET_ID

logger = logging.getLogger(__name__)

# Создаём пустой роутер (нужен для импорта в __init__.py)
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
                return data.get("payment_url")
            else:
                logger.error(f"DonatePay error: {response.status}")
                return None
    except Exception as e:
        logger.error(f"DonatePay exception: {e}")
        return None
