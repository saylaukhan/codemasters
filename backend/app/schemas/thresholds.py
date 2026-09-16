"""Quality thresholds of a measurement (ТЗ п. 11, ADR-004)."""

from pydantic import BaseModel, Field


class ThresholdValues(BaseModel):
    """Limits of the «Норма» status; base values of ТЗ п. 11 are the examples."""

    download_min_mbps: float = Field(ge=0, examples=[20])
    upload_min_mbps: float = Field(ge=0, examples=[20])
    ping_max_ms: float = Field(ge=0, examples=[100])
    jitter_max_ms: float = Field(ge=0, examples=[30])
    packet_loss_max_pct: float = Field(ge=0, le=100, examples=[2])
