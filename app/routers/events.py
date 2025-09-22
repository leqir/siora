from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.google import create_event as g_create_event
from app.google import list_events as g_list_events
from app.models import User
from app.schemas import EventCreate
from app.security import DB, get_current_user

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
def get_events(
    time_min: str = Query(..., description="RFC3339 start"),
    time_max: str = Query(..., description="RFC3339 end"),
    q: str | None = Query(None),
    db: DB = None,
    user: Annotated[User, Depends(get_current_user)] = None,
):
    try:
        items = g_list_events(db, user, time_min=time_min, time_max=time_max, q=q)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("")
def create_event(
    payload: EventCreate,
    db: DB = None,
    user: Annotated[User, Depends(get_current_user)] = None,
):
    try:
        ev = g_create_event(
            db,
            user,
            summary=payload.summary,
            start_iso=payload.start_iso,
            end_iso=payload.end_iso,
            timezone=payload.timezone,
            location=payload.location,
            description=payload.description,
        )
        return {"event": ev}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
