from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    avatar_url: str | None = None


class ConversationCreate(BaseModel):
    title: str | None = "New Chat"


class ConversationOut(BaseModel):
    id: int
    title: str


class MessageCreate(BaseModel):
    conversation_id: int | None = None
    content: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class EventCreate(BaseModel):
    summary: str
    start_iso: str  # RFC3339 like "2025-09-23T15:00:00+10:00"
    end_iso: str
    timezone: str
    location: str | None = None
    description: str | None = None


class EventQuery(BaseModel):
    time_min: str
    time_max: str
    q: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    created_event_id: str | None = None
