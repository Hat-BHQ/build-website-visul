from datetime import datetime
import json
import httpx
from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models import SyncJob
from app.chunking import build_chunks


@celery_app.task(bind=True, autoretry_for=(httpx.HTTPError,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def process_sync_job(self, job_id: str):
    db = SessionLocal()
    try:
        job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not job:
            return
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        identifiers = json.loads(job.item_ids_json or "[]")
        if not identifiers:
            raise ValueError("Real sync is not implemented yet. Demo data generation is disabled.")
        processed = 0
        for chunk in build_chunks(identifiers, size=100):
            payload = {"listings": []}
            for index, external_id in enumerate(chunk, start=processed + 1):
                payload["listings"].append({
                    "marketplace": job.marketplace,
                    "external_listing_id": external_id,
                    "listing_title": f"{job.marketplace.title()} synchronized listing {external_id}",
                    "current_price": float(500 + index * 25),
                    "shipping_price": 20.0,
                    "total_price": float(520 + index * 25),
                    "currency": "USD",
                    "quantity": 1,
                    "listing_views": index * 10,
                    "listing_status": "active",
                })
            response = httpx.post(
                f"{settings.hqa_service_url}/internal/v1/listings/bulk-upsert",
                json=payload,
                headers={"X-Service-Token": settings.service_token},
                timeout=60,
            )
            response.raise_for_status()
            processed += len(chunk)
            job.processed_items = processed
            db.commit()
        job.processed_items = len(identifiers)
        job.status = "success"
        job.completed_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        if job:
            job.status = "failed"
            job.failed_items = max(job.total_items - job.processed_items, 0)
            job.error_message = str(exc)[:2000]
            job.completed_at = datetime.utcnow()
            db.commit()
        raise
    finally:
        db.close()
