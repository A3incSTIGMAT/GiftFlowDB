"""
Инициализация всех обработчиков бота
"""

from .start import router as start_router
from .gifts import router as gifts_router
from .admin import router as admin_router
from .ozon_payments import router as ozon_router

# Список всех роутеров для подключения в main.py
routers = [
    start_router,
    gifts_router,
    admin_router,
    ozon_router
]
