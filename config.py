import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Два отдельных админа
SUPER_ADMIN_ID_1 = int(os.getenv("SUPER_ADMIN_ID_1", "0"))
SUPER_ADMIN_ID_2 = int(os.getenv("SUPER_ADMIN_ID_2", "0"))

# Список всех админов
SUPER_ADMIN_IDS = [id for id in [SUPER_ADMIN_ID_1, SUPER_ADMIN_ID_2] if id != 0]

# Для обратной совместимости
SUPER_ADMIN_ID = SUPER_ADMIN_ID_1 if SUPER_ADMIN_ID_1 != 0 else SUPER_ADMIN_ID_2
SUPPORT_ADMIN_ID = SUPER_ADMIN_ID

CHANNEL_ID = os.getenv("CHANNEL_ID")
DB_PATH = os.getenv("DB_PATH", "/data/gift_bot.db")

# Функция проверки админа
def is_admin(user_id: int) -> bool:
    return user_id in SUPER_ADMIN_IDS

# Ссылки на социальные сети
TWITCH_URL = "https://twitch.tv/lana"
INSTAGRAM_URL = "https://instagram.com/lana"

# Платёжные данные
OZON_CARD_LAST = os.getenv("OZON_CARD_LAST", "4436")
OZON_BANK_NAME = os.getenv("OZON_BANK_NAME", "Озон Банк")
OZON_RECEIVER = os.getenv("OZON_RECEIVER", "Александр Б.")
OZON_SBP_QR_URL = os.getenv("OZON_SBP_QR_URL", "019d2edd-64d5-7781-87ea-fea6bf40d6cf")

# ============ НАСТРОЙКИ ЦЕЛИ ПО УМОЛЧАНИЮ ============
DEFAULT_GOAL_NAME = "Новый компьютер для стримов"
DEFAULT_GOAL_AMOUNT = 250000

# Проверки
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

if not SUPER_ADMIN_IDS:
    raise ValueError("SUPER_ADMIN_ID_1 или SUPER_ADMIN_ID_2 не заданы!")

if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не задан!")
