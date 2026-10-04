from fastapi import APIRouter

from app.api import (
    admin,
    analytics,
    auth,
    dashboard,
    demo,
    health,
    insights,
    orders,
    reference,
    reports,
    telegram,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
# Подсказки идут до /orders/{id}, чтобы «/orders/assist» не принимался за номер наряда
api_router.include_router(insights.router)
api_router.include_router(orders.router)
api_router.include_router(reference.router)
api_router.include_router(admin.router)
api_router.include_router(telegram.router)
api_router.include_router(demo.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
api_router.include_router(dashboard.router)
