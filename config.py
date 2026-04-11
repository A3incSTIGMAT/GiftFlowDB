import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Поддержка нескольких ID через запятую
def parse_ids(ids_str: str) -> list:
    if not ids_str:
        return []
    return [int(x.strip()) for x in ids_str.split(",") if x.strip()]

# Супер-админы (оба имеют полный доступ)
SUPER_ADMIN_IDS = parse_ids(os.getenv("SUPER_ADMIN_ID", ""))

# Для обратной совместимости
SUPER_ADMIN_ID = SUPER_ADMIN_IDS[0] if SUPER_ADMIN_IDS else 0
SUPPORT_ADMIN_ID = SUPER_ADMIN_ID  # для совместимости

CHANNEL_ID = os.getenv("CHANNEL_ID")
DB_PATH = os.getenv("DB_PATH", "/app/gift_bot.db")

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

# Проверки
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

if not SUPER_ADMIN_IDS:
    raise ValueError("SUPER_ADMIN_ID не задан!")

if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не задан!")
