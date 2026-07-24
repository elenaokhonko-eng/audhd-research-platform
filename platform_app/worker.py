from celery import Celery

from platform_app.settings import get_settings

settings = get_settings()
celery_app = Celery("audhd_platform", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_track_started = True
celery_app.conf.worker_prefetch_multiplier = 1


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def advance_research_run(self, run_id: str) -> dict[str, str]:
    """Dispatch one durable workflow stage; stage handlers are added incrementally."""
    return {"run_id": run_id, "status": "queued"}
