from itsdangerous import TimestampSigner, BadSignature
from app.config import settings

_signer = TimestampSigner(settings.SECRET_KEY)

def sign_user_id(user_id: str) -> str:
    return _signer.sign(user_id).decode("utf-8")

def unsign_user_id(token: str) -> str | None:
    try:
        return _signer.unsign(token, max_age=60*60*24*30).decode("utf-8")
    except BadSignature:
        return None

SESSION_COOKIE = "sid"
