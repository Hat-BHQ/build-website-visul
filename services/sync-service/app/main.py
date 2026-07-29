from contextlib import asynccontextmanager
import json
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import Base, engine, get_db
from app.models import SyncJob
from app.schemas import CreateJobRequest
from app.security import require_permission
from app.tasks import process_sync_job


def serialize(item: SyncJob) -> dict:
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Sync Service", version="2.0.0", lifespan=lifespan)


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    db.query(SyncJob).limit(1).all()
    return {"status": "ready", "database": "ok"}


@app.post("/internal/v1/jobs", status_code=202)
def create_job(
    payload: CreateJobRequest,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.sync.run")),
):
    existing = db.query(SyncJob).filter(SyncJob.idempotency_key == payload.idempotency_key).first()
    if existing:
        return serialize(existing)
    unique_ids = list(dict.fromkeys(payload.item_ids))
    job = SyncJob(
        idempotency_key=payload.idempotency_key,
        marketplace=payload.marketplace,
        sync_type=payload.sync_type,
        requested_by=claims["sub"],
        total_items=len(unique_ids) if unique_ids else 5,
        item_ids_json=json.dumps(unique_ids),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    process_sync_job.delay(job.id)
    return serialize(job)


@app.get("/internal/v1/jobs")
def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.sync.view")),
):
    query = db.query(SyncJob)
    total = query.count()
    items = query.order_by(SyncJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [serialize(item) for item in items], "total": total, "page": page, "page_size": page_size}


@app.get("/internal/v1/jobs/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    claims: dict = Depends(require_permission("hqa.sync.view")),
):
    item = db.query(SyncJob).filter(SyncJob.id == job_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Job not found")
    return serialize(item)
