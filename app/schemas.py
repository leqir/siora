from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str | None = None
    picture_url: str | None = None

class ChatIn(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None

class ChatChunk(BaseModel):
    event: str  # "status" | "delta" | "tool" | "done" | "error"
    data: str

class EventCreate(BaseModel):
    title: str = Field(min_length=1)
    start_iso: str  # RFC3339 string
    end_iso: str
    timezone: str
    attendees: list[str] = []

class EventOut(BaseModel):
    id: str
    html_link: str | None = None
    title: str
    start_iso: str
    end_iso: str
