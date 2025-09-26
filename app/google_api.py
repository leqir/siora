from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from fastapi import HTTPException, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User, GoogleToken

GOOGLE_SCOPES: Sequence[str] = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
)

def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "project_id": "calendar-assistant",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }

def new_flow(state: str | None = None) -> Flow:
    flow = Flow.from_client_config(
        _client_config(),
        scopes=list(GOOGLE_SCOPES),
    )
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    if state:
        flow.params["state"] = state
    return flow

async def upsert_user_and_tokens(
    db: AsyncSession,
    email: str,
    name: str | None,
    picture: str | None,
    creds: Credentials,
) -> User:
    # Upsert user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(email=email, name=name, picture_url=picture)
        db.add(user)
        await db.flush()

    # Upsert tokens
    tok = GoogleToken(
        user_id=user.id,
        access_token=creds.token,
        refresh_token=creds.refresh_token or "",  # may be None on subsequent grants
        token_expiry=creds.expiry.replace(tzinfo=timezone.utc).astimezone(timezone.utc),
        scopes=" ".join(creds.scopes or []),
        connected=True,
    )
    await db.merge(tok)
    await db.commit()
    return user

async def load_credentials(db: AsyncSession, user_id: str) -> Credentials:
    res = await db.execute(select(GoogleToken).where(GoogleToken.user_id == user_id))
    row = res.scalar_one_or_none()
    if not row or not row.connected:
        raise HTTPException(status_code=401, detail="Google Calendar not connected")

    creds = Credentials(
        token=row.access_token,
        refresh_token=row.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=row.scopes.split(),
    )
    # Ensure fresh
    if creds.expired and creds.refresh_token:
        creds.refresh(request=None)  # google-auth handles default Request
    return creds

async def calendar_service(db: AsyncSession, user_id: str):
    creds = await load_credentials(db, user_id)
    # Discovery client (v3)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)
