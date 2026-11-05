from fastapi import APIRouter

from app.api.routes import firms, health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(firms.router)
