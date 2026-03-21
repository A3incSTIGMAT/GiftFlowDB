import os

# ==================== TELEGRAM ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", 895844198))
SUPPORT_ADMIN_ID = int(os.getenv("SUPPORT_ADMIN_ID", 7076299389))
ADMIN_IDS = [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]

# ==================== DONATEPAY ====================
DONATEPAY_API_KEY = os.getenv("DONATEPAY_API_KEY")
DONATEPAY_WALLET_ID = os.getenv("DONATEPAY_WALLET_ID", "1472367")

# ==================== СОЦСЕТИ ====================
TWITCH_URL = "https://twitch.tv/lanatwitchh"
INSTAGRAM_URL = "https://instagram.com/lanawolfyy"
DONATEPAY_URL = f"https://donatepay.ru/don/{DONATEPAY_WALLET_ID}"

# ==================== ДАННЫЕ СТРИМЕРШИ ====================
STREAMER_NAME = "Лана"

# ==================== ФИНАНСЫ ====================
# Распределение дохода (от общей суммы доната)
# Например: донат 1000₽ → Лана 470₽, Админ 280₽, Развитие 190₽, Налог 60₽
PROFIT_SPLIT = {
    'lana': 0.47,        # 47% Лана
    'admin': 0.28,       # 28% Админ (ты)
    'development': 0.19, # 19% Развитие проекта
    'tax': 0.06          # 6% Налог
}

# ==================== БАЗА ДАННЫХ ====================
DB_PATH = os.getenv("DB_PATH", "/app/gift_bot.db")
