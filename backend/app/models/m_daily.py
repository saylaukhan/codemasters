"""``m_daily``: continuous aggregate of ``measurements`` by the days of Asia/Almaty (T-19)."""

from app.models.base import Base
from app.models.rollup import MeasurementRollup


class MDaily(MeasurementRollup, Base):
    """Day of a device on a line: analytics over a period and the rating of schools (T-27)."""

    __tablename__ = "m_daily"
