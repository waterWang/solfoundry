from fastapi import APIRouter
from app.api.v1.endpoints import auth, ai_enhancer

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(ai_enhancer.router, prefix="/v1", tags=["ai-enhancer"])
