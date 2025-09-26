from __future__ import annotations
import asyncio
import json
from datetime import datetime, timedelta
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import ChatMessage, User
from app.schemas import ChatIn
from app.utils import SESSION_COOKIE, unsign_user_id
from app.config import settings

router = APIRouter(prefix="/chat", tags=["chat"])

def sse_event(event: str, data: str) -> bytes:
    # Proper SSE framing
    return f"event: {event}\ndata: {data}\n\n".encode("utf-8")

async def get_user_or_401(request: Request, db: AsyncSession) -> User:
    raw = request.cookies.get(SESSION_COOKIE)
    uid = unsign_user_id(raw) if raw else None
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    res = await db.execute(select(User).where(User.id == uid))
    return res.scalar_one()

async def _append_message(db: AsyncSession, user_id: str, role: str, content: str):
    db.add(ChatMessage(user_id=user_id, role=role, content=content))
    await db.commit()

async def _history(db: AsyncSession, user_id: str, limit: int = 20) -> list[dict]:
    res = await db.execute(
        select(ChatMessage).where(ChatMessage.user_id == user_id).order_by(ChatMessage.created_at.desc()).limit(limit)
    )
    msgs = list(reversed(res.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in msgs]

@router.post("/stream")
async def stream_chat(
    request: Request,
    payload: ChatIn,
    db: AsyncSession = Depends(get_db),
):
    user = await get_user_or_401(request, db)
    await _append_message(db, user.id, "user", payload.message)

    async def _gen() -> AsyncGenerator[bytes, None]:
        # 1) thinking
        yield sse_event("status", "thinking")

        # 2) stream model tokens (OpenAI)
        if not settings.OPENAI_API_KEY:
            # Fallback demo stream (no external calls)
            text = "Thanks! I’m connected to your calendar. Ask me things like “What’s on tomorrow?”"
            for ch in text:
                await asyncio.sleep(0.02)
                yield sse_event("delta", ch)
        else:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # Pull recent history to give the model context
            history = await _history(db, user.id, limit=20)
            messages = history + [{"role": "user", "content": payload.message}]

            # Minimal tool-hinting to steer intent:
            system = (
                "You are a calendar assistant. If the user asks about events, call the 'get_events' tool. "
                "If they ask to add something, call 'create_event'. Always confirm in natural language."
            )

            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "get_events",
                        "description": "List events in a time window",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "timeMin": {"type": "string", "description": "RFC3339"},
                                "timeMax": {"type": "string", "description": "RFC3339"},
                                "query": {"type": "string"}
                            },
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "create_event",
                        "description": "Create a calendar event",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "start_iso": {"type": "string"},
                                "end_iso": {"type": "string"},
                                "timezone": {"type": "string"},
                                "attendees": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["title","start_iso","end_iso","timezone"]
                        }
                    }
                },
            ]

            # Stream
            with client.responses.stream(
                model="gpt-4o-mini",
                input=[{"role": "system", "content": system}, *messages],
                tools=tools,
                temperature=0.3,
            ) as stream:
                for event in stream:
                    if event.type == "response.output_text.delta":
                        yield sse_event("delta", event.delta)
                    elif event.type == "response.function_call_arguments.delta":
                        # The model is calling a tool and streaming JSON args
                        yield sse_event("tool", event.delta or "")
                    elif event.type == "response.completed":
                        break

        # 3) done
        yield sse_event("done", "true")

    return StreamingResponse(_gen(), media_type="text/event-stream")
