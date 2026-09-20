"""SQLAlchemy models, one table per module (ADR-003, plan.md §5).

Importing this package registers every table in ``Base.metadata``, which Alembic autogenerate
compares with the database (``alembic/env.py``).
"""

from app.models.agent_release import AgentRelease
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.connection_type import ConnectionType
from app.models.device import Device
from app.models.enrollment_code import EnrollmentCode
from app.models.export import Export
from app.models.heartbeat import Heartbeat
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.incident_rule import IncidentRule
from app.models.line import Line
from app.models.m_daily import MDaily
from app.models.m_hourly import MHourly
from app.models.measurement import Measurement
from app.models.monitoring_point import MonitoringPoint
from app.models.notification import Notification
from app.models.notification_log import NotificationLog
from app.models.outage import Outage
from app.models.provider import Provider
from app.models.region import Region
from app.models.role import Role
from app.models.schedule import Schedule
from app.models.school import School
from app.models.school_contact import SchoolContact
from app.models.system_settings import SystemSettings
from app.models.threshold_profile import ThresholdProfile
from app.models.user import User
from app.models.user_scope import UserScope

__all__ = [
    "AgentRelease",
    "AuditLog",
    "Base",
    "ConnectionType",
    "Device",
    "EnrollmentCode",
    "Export",
    "Heartbeat",
    "Incident",
    "IncidentEvent",
    "IncidentRule",
    "Line",
    "MDaily",
    "MHourly",
    "Measurement",
    "MonitoringPoint",
    "Notification",
    "NotificationLog",
    "Outage",
    "Provider",
    "Region",
    "Role",
    "Schedule",
    "School",
    "SchoolContact",
    "SystemSettings",
    "ThresholdProfile",
    "User",
    "UserScope",
]
