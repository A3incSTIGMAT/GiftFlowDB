import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", 895844198))
SUPPORT_ADMIN_ID = int(os.getenv("SUPPORT_ADMIN_ID", 7076299389))
ADMIN_IDS = [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]

# ==================== TELEGRAM КАНАЛ ====================
CHANNEL_ID = os.getenv("CHANNEL_ID", "@lanatwitchh")

# ==================== СОЦСЕТИ ====================
TWITCH_URL = "https://twitch.tv/lanatwitchh"
INSTAGRAM_URL = "https://instagram.com/lanawolfyy"
DONATEPAY_URL = "https://donatepay.ru/don/1472367"  # оставляем для справки

# ==================== ДАННЫЕ СТРИМЕРШИ ====================
STREAMER_NAME = "Лана"

# ==================== ФИНАНСЫ ====================
PROFIT_SPLIT = {
    'lana': 0.47,
    'admin': 0.28,
    'development': 0.19,
    'tax': 0.06
}

# ==================== БАЗА ДАННЫХ ====================
DB_PATH = os.getenv("DB_PATH", "/app/gift_bot.db")
