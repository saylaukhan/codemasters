"""Codes shared by the API; each alias is a named enum in OpenAPI and in the panel types.

Russian labels live only in ``web/src/lib/labels.ts`` (ADR-013); the API returns codes.
"""

from typing import Literal

# Quality of a measurement or a line, evaluated on the server (ADR-004).
type QualityStatus = Literal["normal", "unstable", "critical", "offline"]

# Status of a school on the map and in lists; ``no_data`` is display-only (ADR-004, ADR-014).
type SchoolStatus = Literal["normal", "unstable", "critical", "offline", "no_data"]

# Connectivity check result of a measurement (ADR-012).
type ConnectionStatus = Literal["online", "offline"]

# Network interface of a measurement; Wi-Fi does not rate the line (ADR-012).
type IfaceType = Literal["ethernet", "wifi", "other"]

# Role of a line at a school (ADR-003).
type LineStatus = Literal["main", "reserve", "disabled"]

# Device blocking keeps its history (ADR-005).
type DeviceStatus = Literal["active", "blocked"]

# Day of the week in Asia/Almaty: working hours of a school, analytics heatmap (ADR-014).
type Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

# Five roles of ТЗ п. 16 (ADR-008): Школа, Район/город, Область, Провайдер, Администратор.
type UserRole = Literal["school", "district", "oblast", "provider", "admin"]
