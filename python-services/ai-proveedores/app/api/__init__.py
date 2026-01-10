"""
API routers for AI Proveedores service.

Este módulo contiene todos los routers HTTP organizados por responsabilidad.
"""
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.api.whatsapp import router as whatsapp_router

__all__ = [
    "health_router",
    "search_router",
    "whatsapp_router",
]
