import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0"))
SUPPORT_ADMIN_ID = int(os.getenv("SUPPORT_ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID")
DB_PATH = os.getenv("DB_PATH", "/app/gift_bot.db")

# Список администраторов (для совместимости)
ADMIN_IDS = [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]

# Ссылки на социальные сети
TWITCH_URL = "https://twitch.tv/lana"
INSTAGRAM_URL = "https://instagram.com/lana"

# Проверка обязательных переменных
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения!")

if SUPER_ADMIN_ID == 0:
    raise ValueError("SUPER_ADMIN_ID не задан в переменных окружения!")

if SUPPORT_ADMIN_ID == 0:
    raise ValueError("SUPPORT_ADMIN_ID не задан в переменных окружения!")

if not CHANNEL_ID:
    raise ValueError("CHANNEL_ID не задан в переменных окружения!")
