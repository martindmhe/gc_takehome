from fastapi import APIRouter

from app.api.routes import auth, cases, firms, health, leads, meta

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(meta.router)
api_router.include_router(firms.router)
api_router.include_router(leads.router)
api_router.include_router(cases.router)
