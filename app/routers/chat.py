from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.google import create_event as g_create_event
from app.google import list_events as g_list_events
from app.models import Conversation, Message, User
from app.schemas import ChatResponse, MessageCreate
from app.security import DB, get_current_user
from app.utils import nlp
from app.utils.llm import draft_assistant_reply

router = APIRouter(prefix="/chat", tags=["chat"])


def get_or_create_conversation(db: Session, user_id: int, conversation_id: int | None) -> Conversation:
    if conversation_id:
        conv = db.query(Conversation).filter(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        ).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv
    conv = Conversation(user_id=user_id, title="Calendar Chat")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_history(db: Session, conversation_id: int, limit: int = 20):
    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in msgs[-limit:]]


@router.post("")
def chat_once(
    payload: MessageCreate,
    db: DB = None,
    user: Annotated[User, Depends(get_current_user)] = None,
) -> ChatResponse:
    conv = get_or_create_conversation(db, user.id, payload.conversation_id)
    # Save user message
    m = Message(conversation_id=conv.id, role="user", content=payload.content)
    db.add(m)
    db.commit()

    text = payload.content.strip()
    hints = {}
    created_event_id = None

    when_range = nlp.parse_when_range(text)
    if "meeting with" in text.lower() and when_range:
        start, end = when_range
        hints["events"] = g_list_events(db, user, time_min=start.isoformat(), time_max=end.isoformat(), q="meeting")
    elif "what's on my calendar" in text.lower() and when_range:
        start, end = when_range
        hints["events"] = g_list_events(db, user, time_min=start.isoformat(), time_max=end.isoformat())
    elif any(w in text.lower() for w in ["add", "create", "schedule"]):
        new_ev = nlp.parse_new_event(text)
        if new_ev:
            ev = g_create_event(
                db,
                user,
                summary=new_ev["title"],
                start_iso=new_ev["start"].isoformat(),
                end_iso=new_ev["end"].isoformat(),
                timezone=new_ev["timezone"],
            )
            created_event_id = ev.get("id")
            hints["created_event"] = ev

    reply = draft_assistant_reply(get_history(db, conv.id), hints=hints)

    ma = Message(conversation_id=conv.id, role="assistant", content=reply)
    db.add(ma)
    db.commit()

    return ChatResponse(reply=reply, conversation_id=conv.id, created_event_id=created_event_id)


@router.get("/stream")
async def chat_stream(
    message: str,
    conversation_id: int | None = None,
    db: DB = None,
    user: Annotated[User, Depends(get_current_user)] = None,
):
    conv = get_or_create_conversation(db, user.id, conversation_id)

    m = Message(conversation_id=conv.id, role="user", content=message)
    db.add(m)
    db.commit()

    hints = {}
    created_event_id = None
    when_range = nlp.parse_when_range(message)
    if "meeting with" in message.lower() and when_range:
        start, end = when_range
        hints["events"] = g_list_events(db, user, time_min=start.isoformat(), time_max=end.isoformat(), q="meeting")
    elif "what's on my calendar" in message.lower() and when_range:
        start, end = when_range
        hints["events"] = g_list_events(db, user, time_min=start.isoformat(), time_max=end.isoformat())
    elif any(w in message.lower() for w in ["add", "create", "schedule"]):
        new_ev = nlp.parse_new_event(message)
        if new_ev:
            ev = g_create_event(
                db,
                user,
                summary=new_ev["title"],
                start_iso=new_ev["start"].isoformat(),
                end_iso=new_ev["end"].isoformat(),
                timezone=new_ev["timezone"],
            )
            created_event_id = ev.get("id")
            hints["created_event"] = ev

    full_text = draft_assistant_reply(get_history(db, conv.id), hints=hints)

    ma = Message(conversation_id=conv.id, role="assistant", content=full_text)
    db.add(ma)
    db.commit()

    async def event_gen() -> AsyncGenerator[bytes, None]:
        yield f"event: status\ndata: {json.dumps({'status': 'thinking'})}\n\n".encode()
        for i in range(0, len(full_text), 40):
            chunk = full_text[i:i+40]
            yield f"event: delta\ndata: {json.dumps({'text': chunk})}\n\n".encode()
            await asyncio.sleep(0.02)
        yield f"event: done\ndata: {json.dumps({'conversation_id': conv.id, 'created_event_id': created_event_id})}\n\n".encode()

    return StreamingResponse(event_gen(), media_type="text/event-stream")
