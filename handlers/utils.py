from config import PROFIT_SPLIT

def calculate_profit_shares(fee_amount: float) -> dict:
    return {
        'lana': fee_amount * PROFIT_SPLIT['lana'],
        'admin': fee_amount * PROFIT_SPLIT['admin'],
        'development': fee_amount * PROFIT_SPLIT['development'],
        'tax': fee_amount * PROFIT_SPLIT['tax']
    }

def format_profit_text(shares: dict) -> str:
    return (f"📈 <b>Распределение:</b>\n"
            f"👤 Лана (47%): {int(shares['lana'])}₽\n"
            f"👤 Я (28%): {int(shares['admin'])}₽\n"
            f"🚀 Развитие (19%): {int(shares['development'])}₽\n"
            f"📋 Налог (6%): {int(shares['tax'])}₽")
