"""SQLAlchemy models, one table per module (ADR-003, plan.md §5).

Importing this package registers every table in ``Base.metadata``, which Alembic autogenerate
compares with the database (``alembic/env.py``).
"""

from app.models.base import Base
from app.models.connection_type import ConnectionType
from app.models.device import Device
from app.models.enrollment_code import EnrollmentCode
from app.models.heartbeat import Heartbeat
from app.models.line import Line
from app.models.measurement import Measurement
from app.models.monitoring_point import MonitoringPoint
from app.models.outage import Outage
from app.models.provider import Provider
from app.models.region import Region
from app.models.school import School
from app.models.school_contact import SchoolContact

__all__ = [
    "Base",
    "ConnectionType",
    "Device",
    "EnrollmentCode",
    "Heartbeat",
    "Line",
    "Measurement",
    "MonitoringPoint",
    "Outage",
    "Provider",
    "Region",
    "School",
    "SchoolContact",
]
