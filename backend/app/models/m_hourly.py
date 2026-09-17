"""``m_hourly``: continuous aggregate of ``measurements`` by the hours of Asia/Almaty (T-19)."""

from app.models.base import Base
from app.models.rollup import MeasurementRollup


class MHourly(MeasurementRollup, Base):
    """Hour of a device on a line: the heat map «час × день» of ТЗ п. 5 is built on it."""

    __tablename__ = "m_hourly"
