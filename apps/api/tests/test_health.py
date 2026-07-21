from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app

test_engine = create_engine("sqlite:///:memory:")


def override_db() -> Iterator[Session]:
    with Session(test_engine) as session:
        yield session


app.dependency_overrides[get_db] = override_db
client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_queries_database() -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "reachable"}

