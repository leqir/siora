from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import engine
from app.models import Base

from app.auth import router as auth_router
from app.calendar_api import router as calendar_router
from app.chat import router as chat_router

app = FastAPI(title="AI Calendar Assistant (Backend)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    # create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(auth_router)
app.include_router(calendar_router)
app.include_router(chat_router)
