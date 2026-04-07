from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ========== REPLY КЛАВИАТУРЫ ==========

def get_main_keyboard():
    """Клавиатура главного меню для пользователей"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📺 Twitch"), KeyboardButton(text="📷 Instagram")],
            [KeyboardButton(text="🎁 Каталог подарков")],
            [KeyboardButton(text="🏆 Топ героев"), KeyboardButton(text="🎁 О конкурсе")],
            [KeyboardButton(text="🆘 Помощь"), KeyboardButton(text="👑 Админ-панель")],
            [KeyboardButton(text="Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_keyboard():
    """Клавиатура админ-панели"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Управление заказами")],
            [KeyboardButton(text="🖼️ Управление галереей")],
            [KeyboardButton(text="✏️ Создать пост"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="🏆 Топ героев (админ)"), KeyboardButton(text="➕ Добавить подарок")],
            [KeyboardButton(text="🎁 Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_cancel_keyboard():
    """Клавиатура для отмены действия"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard


# ========== INLINE КЛАВИАТУРЫ ==========

def get_gifts_keyboard(gifts):
    """Клавиатура каталога подарков"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for gift in gifts:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{gift['icon']} {gift['name']} — {gift['price']}₽",
                callback_data=f"gift_{gift['id']}"
            )
        ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")
    ])
    return keyboard

def get_payment_keyboard(gift_id, gift_name, gift_price):
    """Клавиатура оплаты для подарка"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Оплатить картой", callback_data=f"pay_card_{gift_id}"),
            InlineKeyboardButton(text="📱 СБП/QR-код", callback_data=f"pay_sbp_{gift_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад к подаркам", callback_data="back_to_gifts")
        ]
    ])
    return keyboard

def get_payment_details_keyboard(gift_id):
    """Клавиатура с реквизитами для оплаты"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Я оплатил(а)", callback_data=f"confirm_payment_{gift_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_gifts")
        ]
    ])
    return keyboard

def get_admin_orders_keyboard(orders):
    """Клавиатура для управления заказами (админка)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for order in orders[:10]:
        status_emoji = "✅" if order.get('status') == 'paid' else "⏳"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{status_emoji} Заказ #{order['id']} — {order['gift_name']} — {order['amount']}₽",
                callback_data=f"order_{order['id']}"
            )
        ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_orders")
    ])
    return keyboard

def get_order_actions_keyboard(order_id):
    """Клавиатура действий с заказом"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 Назад к заказам", callback_data="back_to_orders")
        ]
    ])
    return keyboard

def get_gallery_keyboard(images):
    """Клавиатура галереи (админка)"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for img in images[:10]:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🖼️ {img.get('description', 'Без описания')[:20]}",
                callback_data=f"gallery_{img['id']}"
            )
        ])
    keyboard.inline_keyboard.extend([
        [InlineKeyboardButton(text="➕ Добавить фото", callback_data="add_gallery_photo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_admin")]
    ])
    return keyboard

def get_confirm_post_keyboard():
    """Клавиатура подтверждения публикации поста"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data="confirm_post"),
            InlineKeyboardButton(text="✏️ Редактировать текст", callback_data="edit_post_text"),
            InlineKeyboardButton(text="🖼️ Изменить фото", callback_data="edit_post_photo")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_post")
        ]
    ])
    return keyboard

def get_back_to_admin_keyboard():
    """Кнопка возврата в админку"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="back_to_admin")]
    ])
    return keyboard
