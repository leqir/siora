from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Use this type alias in routes
DB = Annotated[Session, Depends(get_db)]


def create_jwt(user_id: int, expires_minutes: int | None = None) -> str:
    if expires_minutes is None:
        expires_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    exp = datetime.now(tz=UTC) + timedelta(minutes=expires_minutes)
    payload = {"sub": str(user_id), "exp": exp}
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token


def get_current_user(request: Request, db: DB) -> User:
    token: str | None = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        data = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = int(data["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
