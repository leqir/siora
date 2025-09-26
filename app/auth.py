from fastapi import APIRouter, Depends, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from googleapiclient.discovery import build
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.db import get_db
from app.google_api import new_flow, upsert_user_and_tokens
from app.models import User, Base
from app.utils import sign_user_id, SESSION_COOKIE
from app.config import settings
from sqlalchemy import select

router = APIRouter(prefix="/auth/google", tags=["auth"])

@router.get("/authorize")
async def authorize():
    flow = new_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # ensures refresh_token
    )
    # Redirect to Google
    return RedirectResponse(url=auth_url)

@router.get("/callback")
async def callback(request: Request, db: AsyncSession = Depends(get_db)):
    # Recreate flow to exchange code
    flow = new_flow()
    # Parse full URL including code & state
    flow.fetch_token(authorization_response=str(request.url))

    creds = flow.credentials

    # Verify ID token for profile details
    _req = google_requests.Request()
    idinfo = id_token.verify_oauth2_token(
        creds.id_token,
        _req,
        settings.GOOGLE_CLIENT_ID,
    )
    email = idinfo.get("email")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    user = await upsert_user_and_tokens(db, email=email, name=name, picture=picture, creds=creds)

    # Set a signed cookie so subsequent requests know who you are
    resp = RedirectResponse(url=f"{settings.FRONTEND_URL}/connected")
    resp.set_cookie(
        key=SESSION_COOKIE,
        value=sign_user_id(user.id),
        httponly=True,
        secure=False,  # True in production (https)
        samesite="lax",
        max_age=60*60*24*30,
        path="/",
    )
    return resp

@router.get("/me")
async def me(request: Request, db: AsyncSession = Depends(get_db)):
    from app.utils import unsign_user_id
    raw = request.cookies.get(SESSION_COOKIE)
    uid = unsign_user_id(raw) if raw else None
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    from app.models import User
    res = await db.execute(select(User).where(User.id == uid))
    u = res.scalar_one()
    return {"id": u.id, "email": u.email, "name": u.name, "picture_url": u.picture_url}
