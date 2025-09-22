from __future__ import annotations

import time

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.config import settings
from app.models import OAuthAccount, User

# Scopes: profile/email + Calendar (can reduce to .events if you want narrower)
SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar",
]

def make_flow(state: str | None = None) -> Flow:
    # use explicit client dict (keeps secrets server-side)
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "project_id": "calendar-assistant",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=f"{settings.BACKEND_URL}/auth/google/callback",
        state=state,
    )
    return flow


def upsert_google_oauth(
    db: Session,
    user: User,
    provider_account_id: str,
    access_token: str,
    refresh_token: str | None,
    expires_in: int | None,
    scope: str | None,
):
    expires_at = int(time.time()) + int(expires_in or 3600)
    acct = (
        db.query(OAuthAccount)
        .filter(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == "google",
            OAuthAccount.provider_account_id == provider_account_id,
        )
        .first()
    )
    if acct:
        acct.access_token = access_token
        if refresh_token:  # refresh_token may be None on subsequent consent
            acct.refresh_token = refresh_token
        acct.expires_at = expires_at
        acct.scope = scope
    else:
        acct = OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_account_id=provider_account_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=scope,
        )
        db.add(acct)
    db.commit()
    db.refresh(acct)
    return acct


def credentials_for_user(db: Session, user: User) -> Credentials:
    acct = (
        db.query(OAuthAccount)
        .filter(OAuthAccount.user_id == user.id, OAuthAccount.provider == "google")
        .first()
    )
    if not acct:
        raise RuntimeError("Google account not connected")

    creds = Credentials(
        token=acct.access_token,
        refresh_token=acct.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    # refresh if needed
    if acct.expires_at and acct.expires_at <= int(time.time()) + 60:
        request = GoogleRequest()
        creds.refresh(request)
        # persist new token + expiry
        acct.access_token = creds.token
        acct.expires_at = int(time.time()) + int(creds.expiry.timestamp() - time.time())
        db.commit()
    return creds


def calendar_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_events(db: Session, user: User, time_min: str, time_max: str, q: str | None = None):
    service = calendar_service(credentials_for_user(db, user))
    kwargs = {"calendarId": "primary", "timeMin": time_min, "timeMax": time_max, "singleEvents": True, "orderBy": "startTime"}
    if q:
        kwargs["q"] = q
    events_result = service.events().list(**kwargs).execute()
    return events_result.get("items", [])


def create_event(
    db: Session,
    user: User,
    summary: str,
    start_iso: str,
    end_iso: str,
    timezone: str,
    location: str | None = None,
    description: str | None = None,
):
    service = calendar_service(credentials_for_user(db, user))
    body = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    if location:
        body["location"] = location
    if description:
        body["description"] = description
    event = service.events().insert(calendarId="primary", body=body).execute()
    return event
