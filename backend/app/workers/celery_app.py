"""Celery application: ``celery -A app.workers.celery_app worker|beat``.

Broker and result backend are Redis (``Settings.redis_url``). Scheduled tasks are stored in
UTC and displayed in the school time zone (ADR-014).

``install_worker_metrics`` connects the task signals and, when the worker starts, Sentry and
the HTTP server of the metrics (``app/core/observability.py``, T-54).
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.observability import install_worker_metrics

settings = get_settings()

install_worker_metrics()

celery_app = Celery(
    "vko_monitor",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.contracts",
        "app.workers.tasks.digest",
        "app.workers.tasks.exports",
        "app.workers.tasks.incidents",
    ],
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
        # Incidents (T-40): the silence of the heartbeat is judged against 15 minutes of
        # ``offline_after_s``, so 5 minutes keep «Нет соединения» on time (ADR-007).
        "detect-incidents": {
            "task": "incidents.detect_all",
            "schedule": 5 * 60,
        },
        # «Устранён» → «Закрыт» after 24 hours (T-41): a quarter of an hour late is on time.
        "close-resolved-incidents": {
            "task": "incidents.close_resolved",
            "schedule": 15 * 60,
        },
        # Сводка для руководителя (T-67): раз в час задача берёт рассылки, чей день недели и
        # час совпали с текущим моментом в settings.timezone; час — самая мелкая единица
        # расписания рассылки, поэтому чаще спрашивать нечего.
        "send-due-digests": {
            "task": "digest.send_due",
            "schedule": crontab(minute=0),
        },
        # Files of exports live for days (T-33): an hour late is as good as on time.
        "purge-expired-exports": {
            "task": "exports.purge_expired",
            "schedule": 60 * 60,
        },
    },
)
