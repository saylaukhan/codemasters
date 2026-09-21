// Geometry of the bar «fact against the threshold» (DESIGN.md §3.10, §3.27). Pure: the component
// only paints what this returns, so the arithmetic is testable without a DOM.

export interface FactBarInput {
  /** The measured value; `null` when there is no measurement yet. */
  value: number | null | undefined
  /** Right end of the track: the scale the bar is read against, e.g. the contract plus a margin. */
  scale: number
  /** Norm from the thresholds of the server (ADR-004); without it the norm tick is not drawn. */
  threshold?: number | null
  /** Contract value (ТЗ п. 14); without it the contract tick is not drawn. */
  contract?: number | null
}

export interface FactBarGeometry {
  /** Width of the fill, 0–100; a value above the scale clamps to the full track. */
  fillPct: number
  /** Position of the norm tick, 0–100, or `null` when there is no norm to show. */
  thresholdPct: number | null
  /** Position of the contract tick, 0–100, or `null` when there is no contract. */
  contractPct: number | null
}

/** Share of the track, clamped to it; a scale that is not a positive number gives nothing. */
function position(value: number | null | undefined, scale: number): number | null {
  if (value === null || value === undefined || !Number.isFinite(value)) return null
  if (!Number.isFinite(scale) || scale <= 0) return null
  return Math.min(100, Math.max(0, (value / scale) * 100))
}

/**
 * Where the fill ends and where the two ticks stand, in per cent of the track. A value above the
 * scale clamps instead of overflowing the card; a missing threshold or contract yields `null`, and
 * the component draws no tick for it (DESIGN.md §3.27: ping has only the norm tick).
 */
export function factBarGeometry({ value, scale, threshold, contract }: FactBarInput): FactBarGeometry {
  return {
    fillPct: position(value, scale) ?? 0,
    thresholdPct: position(threshold, scale),
    contractPct: position(contract, scale),
  }
}
