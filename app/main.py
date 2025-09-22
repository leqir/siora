from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import auth, chat, events

app = FastAPI(title="Calendar Assistant Backend", version="0.1.0")

# Create tables on boot (simple for this guide; consider Alembic migrations in production)
Base.metadata.create_all(bind=engine)

# CORS: allow your Vercel frontend origin
origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(chat.router)


@app.get("/")
def root():
    return {"ok": True, "service": "calendar-assistant-backend"}
