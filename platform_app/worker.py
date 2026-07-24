from celery import Celery

from uuid import UUID

from platform_app.database import SessionLocal
from platform_app.pipeline import PipelineRunner
from platform_app.settings import get_settings

settings = get_settings()
celery_app = Celery("audhd_platform", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_track_started = True
celery_app.conf.worker_prefetch_multiplier = 1


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def advance_research_run(self, run_id: str) -> dict[str, str]:
    """Execute exactly one idempotent workflow stage, then persist its transition."""
    with SessionLocal() as session:
        return PipelineRunner(session, settings).execute_current_stage(UUID(run_id))
