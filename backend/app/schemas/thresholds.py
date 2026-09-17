"""Quality thresholds of a measurement (ТЗ п. 11, ADR-004)."""

from pydantic import BaseModel, Field

from app.schemas.statuses import ProfileScope


class ThresholdValues(BaseModel):
    """Limits of the «Норма» status; base values of ТЗ п. 11 are the examples."""

    download_min_mbps: float = Field(ge=0, examples=[20])
    upload_min_mbps: float = Field(ge=0, examples=[20])
    ping_max_ms: float = Field(ge=0, examples=[100])
    jitter_max_ms: float = Field(ge=0, examples=[30])
    packet_loss_max_pct: float = Field(ge=0, le=100, examples=[2])


class MetricBreach(BaseModel):
    """One metric past its limit and how far past it is, in percent of the limit (plan.md §6).

    ``deviation_pct`` is empty when the limit itself is zero — «никаких потерь» has no percent,
    so any breach of it counts as a gross one.
    """

    metric: str = Field(examples=["ping_ms"])
    value: float = Field(examples=[140])
    limit: float = Field(examples=[100])
    deviation_pct: float | None = Field(default=None, examples=[40])


class ThresholdsSnapshot(ThresholdValues):
    """Thresholds a measurement was judged by, stored inside the measurement (ТЗ п. 11).

    A later change of the profile never touches it: the record keeps the numbers of its own
    moment, so a dispute with a provider is settled by the record alone (ADR-004). The contract
    values of the line are here for the same reason — ``contract_ok`` says yes or no, the
    snapshot says against what.
    """

    profile_id: int
    profile_scope: ProfileScope
    unstable_deviation_pct: float = Field(ge=0, examples=[30])
    contract_down_mbps: float | None = None
    contract_up_mbps: float | None = None
    # Wi-Fi measures the air, not the line, so it rates neither the line nor the contract.
    rates_line: bool = True
    breaches: list[MetricBreach] = Field(default_factory=list)
