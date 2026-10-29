import base64
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User
from app.security import (
    authenticate,
    create_token,
    hash_password,
    read_token,
    verify_password,
)

PASSWORD = "correct-horse-battery"


@pytest.fixture
def settings() -> Settings:
    return Settings(auth_secret="test-secret", auth_token_ttl_minutes=60)


@pytest.fixture
def user(db_session: Session) -> User:
    record = User(
        email="operator@causaops.test",
        display_name="On-call operator",
        password_hash=hash_password(PASSWORD),
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def test_password_hash_round_trip() -> None:
    stored = hash_password(PASSWORD)
    assert stored.startswith("scrypt$")
    assert PASSWORD not in stored
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong-password", stored)


def test_each_hash_uses_a_fresh_salt() -> None:
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_malformed_hash_is_rejected_without_raising() -> None:
    assert not verify_password(PASSWORD, "not-a-hash")
    assert not verify_password(PASSWORD, "md5$1$2$3$4$5")


def test_token_round_trip(settings: Settings) -> None:
    user_id = uuid.uuid4()
    assert read_token(create_token(user_id, settings), settings) == user_id


def test_token_signed_with_another_secret_is_rejected(settings: Settings) -> None:
    other = Settings(auth_secret="another-secret")
    assert read_token(create_token(uuid.uuid4(), other), settings) is None


def test_tampered_and_malformed_tokens_are_rejected(settings: Settings) -> None:
    token = create_token(uuid.uuid4(), settings)
    body, signature = token.split(".")
    assert read_token(f"{body}x.{signature}", settings) is None
    assert read_token("garbage", settings) is None
    assert read_token("", settings) is None


def test_expired_token_is_rejected(settings: Settings) -> None:
    expired = Settings(auth_secret=settings.auth_secret, auth_token_ttl_minutes=-1)
    assert read_token(create_token(uuid.uuid4(), expired), settings) is None


def test_authenticate_accepts_the_right_password(db_session: Session, user: User) -> None:
    assert authenticate(db_session, user.email, PASSWORD) is not None
    assert authenticate(db_session, "OPERATOR@CAUSAOPS.TEST", PASSWORD) is not None
    assert authenticate(db_session, user.email, "wrong-password") is None
    assert authenticate(db_session, "nobody@causaops.test", PASSWORD) is None


def test_authenticate_rejects_a_deactivated_user(db_session: Session, user: User) -> None:
    user.is_active = False
    db_session.commit()
    assert authenticate(db_session, user.email, PASSWORD) is None


def test_login_returns_a_usable_token(client: TestClient, user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == user.email
    assert "password_hash" not in body["user"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["display_name"] == "On-call operator"


def test_login_failures_do_not_reveal_whether_the_email_exists(
    client: TestClient, user: User
) -> None:
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "wrong-password"},
    )
    unknown_email = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@causaops.test", "password": PASSWORD},
    )
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_protected_route_requires_a_valid_token(client: TestClient, user: User) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code
        == 401
    )


def test_token_for_a_deleted_user_is_rejected(
    client: TestClient, db_session: Session, user: User
) -> None:
    token = create_token(user.id, Settings())
    db_session.delete(user)
    db_session.commit()
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_development_secret_is_refused_outside_development() -> None:
    with pytest.raises(ValueError, match="AUTH_SECRET"):
        Settings(environment="production")
    Settings(environment="production", auth_secret="a-real-secret")


def test_token_expiry_follows_the_configured_ttl(settings: Settings) -> None:
    before = datetime.now(UTC)
    body = create_token(uuid.uuid4(), settings).split(".")[0]
    payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
    expires_at = datetime.fromtimestamp(int(payload.rsplit(":", 1)[1]), tz=UTC)
    assert before + timedelta(minutes=59) < expires_at <= before + timedelta(minutes=61)
