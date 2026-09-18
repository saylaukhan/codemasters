"""Celery application: ``celery -A app.workers.celery_app worker|beat``.

Broker and result backend are Redis (``Settings.redis_url``). Scheduled tasks are stored in
UTC and displayed in the school time zone (ADR-014); the incident schedule arrives in T-40.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "vko_monitor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks.contracts"],
)
celery_app.conf.update(
    timezone=settings.tz,
    enable_utc=True,
    beat_schedule={
        # Sustained mismatch with the contract (T-29): a window of days moves slowly, a quarter
        # of an hour is fresh enough for the card and the analytics.
        "recompute-contract-compliance": {
            "task": "contracts.recompute_compliance",
            "schedule": 15 * 60,
        },
    },
)
