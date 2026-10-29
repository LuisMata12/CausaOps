import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models import User

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32

bearer_scheme = HTTPBearer(auto_error=False)

UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Authentication required",
    headers={"WWW-Authenticate": "Bearer"},
)


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n, r, p, salt, digest = stored.split("$")
        if algorithm != "scrypt":
            return False
        expected = _decode(digest)
        candidate = hashlib.scrypt(
            password.encode(),
            salt=_decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except ValueError:
        return False
    return hmac.compare_digest(candidate, expected)


def _sign(payload: str, settings: Settings) -> bytes:
    return hmac.new(settings.auth_secret.encode(), payload.encode(), hashlib.sha256).digest()


def create_token(user_id: uuid.UUID, settings: Settings) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.auth_token_ttl_minutes)
    payload = f"{user_id}:{int(expires_at.timestamp())}"
    return f"{_encode(payload.encode())}.{_encode(_sign(payload, settings))}"


def read_token(token: str, settings: Settings) -> uuid.UUID | None:
    """Return the user id carried by a valid, unexpired token, otherwise None."""
    try:
        body, signature = token.split(".")
        payload = _decode(body).decode()
        user_id, expires_at = payload.rsplit(":", 1)
        if not hmac.compare_digest(_decode(signature), _sign(payload, settings)):
            return None
        if int(expires_at) < datetime.now(UTC).timestamp():
            return None
        return uuid.UUID(user_id)
    except (ValueError, UnicodeDecodeError):
        return None


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the human behind a request. Every state-changing action depends on this."""
    if credentials is None:
        raise UNAUTHENTICATED
    user_id = read_token(credentials.credentials, settings)
    if user_id is None:
        raise UNAUTHENTICATED
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UNAUTHENTICATED
    return user
