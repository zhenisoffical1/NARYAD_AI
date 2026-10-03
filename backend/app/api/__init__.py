from fastapi import APIRouter

from app.api import admin, auth, health, orders, reference

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(orders.router)
api_router.include_router(reference.router)
api_router.include_router(admin.router)
