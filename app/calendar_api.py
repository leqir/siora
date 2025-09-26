from datetime import datetime
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.schemas import EventCreate, EventOut
from app.utils import SESSION_COOKIE, unsign_user_id
from app.google_api import calendar_service
from dateutil import parser as dtparse

router = APIRouter(prefix="/calendar", tags=["calendar"])

def _require_user_id(request: Request) -> str:
    raw = request.cookies.get(SESSION_COOKIE)
    uid = unsign_user_id(raw) if raw else None
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return uid

@router.get("/events", response_model=list[EventOut])
async def list_events(
    request: Request,
    timeMin: str | None = None,  # RFC3339
    timeMax: str | None = None,
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    uid = _require_user_id(request)
    svc = await calendar_service(db, uid)

    params = dict(
        calendarId="primary",
        singleEvents=True,
        orderBy="startTime",
        maxResults=50,
    )
    if timeMin: params["timeMin"] = timeMin
    if timeMax: params["timeMax"] = timeMax
    if q: params["q"] = q

    items = svc.events().list(**params).execute().get("items", [])
    events: list[EventOut] = []
    for it in items:
        start = (it.get("start") or {}).get("dateTime") or (it.get("start") or {}).get("date")
        end = (it.get("end") or {}).get("dateTime") or (it.get("end") or {}).get("date")
        events.append(EventOut(
            id=it["id"],
            html_link=it.get("htmlLink"),
            title=it.get("summary", "(no title)"),
            start_iso=start,
            end_iso=end,
        ))
    return events

@router.post("/events", response_model=EventOut)
async def create_event(
    request: Request,
    payload: EventCreate,
    db: AsyncSession = Depends(get_db),
):
    uid = _require_user_id(request)
    svc = await calendar_service(db, uid)

    body = {
        "summary": payload.title,
        "start": {"dateTime": payload.start_iso, "timeZone": payload.timezone},
        "end": {"dateTime": payload.end_iso, "timeZone": payload.timezone},
        "attendees": [{"email": a} for a in payload.attendees],
    }
    created = svc.events().insert(calendarId="primary", body=body).execute()
    return EventOut(
        id=created["id"],
        html_link=created.get("htmlLink"),
        title=created.get("summary", ""),
        start_iso=created["start"].get("dateTime") or created["start"].get("date"),
        end_iso=created["end"].get("dateTime") or created["end"].get("date"),
    )
