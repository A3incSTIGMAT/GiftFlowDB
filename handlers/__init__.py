from .start import router as start_router
from .gifts import router as gifts_router
from .admin import router as admin_router
from .donatepay import router as donatepay_router

# Объединяем все роутеры
routers = [start_router, gifts_router, admin_router, donatepay_router]
