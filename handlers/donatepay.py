import aiohttp
import logging
from aiogram import Router

logger = logging.getLogger(__name__)

router = Router()


async def create_donatepay_invoice(amount: int, description: str, user_id: int) -> str:
    """Создаёт счёт в DonatePay и возвращает ссылку на оплату"""
    try:
        from config import DONATEPAY_API_KEY, DONATEPAY_WALLET_ID
        
        if not DONATEPAY_API_KEY:
            logger.error("DONATEPAY_API_KEY не настроен!")
            return None
        
        if not DONATEPAY_WALLET_ID:
            logger.error("DONATEPAY_WALLET_ID не настроен!")
            return None
        
        logger.info(f"Создаём счёт: {amount}₽ за {description} для user_{user_id}")
        
        # Пробуем разные версии API
        endpoints = [
            "https://donatepay.ru/api/v2/invoice/create",
            "https://donatepay.ru/api/invoice/create",
            "https://donatepay.ru/api/v1/invoice/create"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    response = await session.post(
                        endpoint,
                        headers={"Authorization": f"Bearer {DONATEPAY_API_KEY}"},
                        json={
                            "amount": amount,
                            "currency": "RUB",
                            "description": description,
                            "user_id": user_id,
                            "wallet_id": DONATEPAY_WALLET_ID
                        }
                    )
                    
                    logger.info(f"DonatePay {endpoint}: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"✅ Invoice created: {data}")
                        return data.get("payment_url")
                    else:
                        error_text = await response.text()
                        logger.warning(f"{endpoint} error {response.status}: {error_text}")
                        
                except Exception as e:
                    logger.warning(f"{endpoint} exception: {e}")
                    continue
            
            # Если ни один эндпоинт не сработал
            logger.error("Все API эндпоинты DonatePay не отвечают")
            return None
                
    except Exception as e:
        logger.error(f"DonatePay exception: {e}")
        return None


async def check_donatepay_invoice(invoice_id: str) -> dict:
    """Проверяет статус счёта в DonatePay"""
    try:
        from config import DONATEPAY_API_KEY
        
        endpoints = [
            f"https://donatepay.ru/api/v2/invoice/info?invoice_id={invoice_id}",
            f"https://donatepay.ru/api/invoice/info?invoice_id={invoice_id}",
            f"https://donatepay.ru/api/v1/invoice/info?invoice_id={invoice_id}"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    response = await session.get(
                        endpoint,
                        headers={"Authorization": f"Bearer {DONATEPAY_API_KEY}"}
                    )
                    
                    if response.status == 200:
                        data = await response.json()
                        return data
                        
                except Exception as e:
                    logger.warning(f"Check endpoint error: {e}")
                    continue
            
            return None
            
    except Exception as e:
        logger.error(f"DonatePay check exception: {e}")
        return None
