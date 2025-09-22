from __future__ import annotations

import base64
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.config import settings
from app.google import make_flow, upsert_google_oauth
from app.models import User
from app.security import create_jwt, get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# A tiny opaque state: we encode a JSON { "next": FRONTEND_URL } to carry return target
def encode_state(next_url: str) -> str:
    return base64.urlsafe_b64encode(json.dumps({"next": next_url}).encode()).decode()

def decode_state(state: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(state + "===").decode())


@router.get("/google/start")
def google_start(next: str | None = None):
    flow = make_flow(state=encode_state(next or settings.FRONTEND_URL))
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",  # force refresh_token on first grant
        include_granted_scopes="true",
    )
    return {"auth_url": auth_url}


@router.get("/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db), response: Response = None):
    flow = make_flow(state=state)
    flow.fetch_token(code=code)
    creds = flow.credentials  # contains token, refresh_token, expiry, id_token, scopes

    if not creds.id_token:
        raise HTTPException(status_code=400, detail="Missing id_token")

    idinfo = id_token.verify_oauth2_token(creds.id_token, GoogleRequest(), settings.GOOGLE_CLIENT_ID)
    # idinfo contains 'sub', 'email', 'name', 'picture'
    sub = idinfo["sub"]
    email = idinfo.get("email")
    name = idinfo.get("name")
    picture = idinfo.get("picture")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, name=name, avatar_url=picture)
        db.add(user)
        db.commit()
        db.refresh(user)

    upsert_google_oauth(
        db,
        user=user,
        provider_account_id=sub,
        access_token=creds.token,
        refresh_token=getattr(creds, "refresh_token", None),
        expires_in=int(creds.expiry.timestamp()) - int(creds._expiry) if hasattr(creds, "_expiry") else 3600,
        scope=" ".join(getattr(creds, "scopes", []) or []),
    )

    jwt_token = create_jwt(user.id)
    # Set HttpOnly cookie accessible by both dev & prod (adjust domain in prod if you use a custom domain)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=jwt_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=60 * 60 * 24 * 14,
    )

    target = decode_state(state).get("next", settings.FRONTEND_URL)
    # Minimal HTML page to bounce back to frontend
    return Response(
        content=f"<script>window.location='{target}';</script>",
        media_type="text/html",
    )


@router.get("/me")
def me(db: Session = Depends(get_db), token=None, response: Response = None):
    # If you want, add a dependency to fetch current user like: get_current_user
    return {"ok": True}
