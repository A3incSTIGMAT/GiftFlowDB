from .start import router as start_router
from .gifts import router as gifts_router
from .admin import router as admin_router

# Список всех роутеров (без donatepay)
routers = [
    start_router,
    gifts_router,
    admin_router
]
