import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", 895844198))
SUPPORT_ADMIN_ID = int(os.getenv("SUPPORT_ADMIN_ID", 7076299389))
ADMIN_IDS = [SUPER_ADMIN_ID, SUPPORT_ADMIN_ID]

DONATEPAY_API_KEY = os.getenv("DONATEPAY_API_KEY")
DONATEPAY_WALLET_ID = os.getenv("DONATEPAY_WALLET_ID", "1472367")

TWITCH_URL = "https://twitch.tv/lanatwitchh"
INSTAGRAM_URL = "https://instagram.com/lanawolfyy"
DONATEPAY_URL = "https://donatepay.ru/don/1472367"

STREAMER_NAME = "Лана"

FEE_PERCENT = 0.10
PROFIT_SPLIT = {
    'lana': 0.47,
    'admin': 0.28,
    'development': 0.19,
    'tax': 0.06
}
