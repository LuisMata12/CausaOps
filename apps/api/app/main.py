from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.ingestion import router as ingestion_router
from app.schemas import LiveResponse, ReadyResponse

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(ingestion_router)


@app.get("/health/live", response_model=LiveResponse, tags=["health"])
def live() -> LiveResponse:
    return LiveResponse(status="ok", service=settings.app_name, environment=settings.environment)


@app.get("/health/ready", response_model=ReadyResponse, tags=["health"])
def ready(db: Session = Depends(get_db)) -> ReadyResponse:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    return ReadyResponse(status="ready", database="reachable")
