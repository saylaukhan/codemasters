"""Celery application: ``celery -A app.workers.celery_app worker|beat``.

Broker and result backend are Redis (``Settings.redis_url``). Scheduled tasks are stored in
UTC and displayed in the school time zone (ADR-014); the beat schedule is filled in T-40.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("vko_monitor", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    timezone=settings.tz,
    enable_utc=True,
    beat_schedule={},
)
