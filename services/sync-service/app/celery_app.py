from celery import Celery
from app.config import settings

celery_app = Celery("hq-sync", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=1800,
    task_soft_time_limit=1700,
    broker_connection_retry_on_startup=True,
)
celery_app.autodiscover_tasks(["app"])
