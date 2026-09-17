package probe

import (
	"slices"
	"time"
)

// Series is one ping series: the round-trip times of the answered probes in
// the order the probes were sent, and how many probes were sent.
type Series struct {
	RTTs []time.Duration
	Sent int
}

// Stats are the ping metrics of a series (ADR-012). With no answers PingMs and
// JitterMs are zero and mean "no value", LossPct is 100.
type Stats struct {
	// PingMs is the median RTT.
	PingMs float64
	// JitterMs is the mean |RTTᵢ − RTTᵢ₋₁| over consecutive answers (RFC 3550).
	JitterMs float64
	// LossPct is the share of probes without an answer, 0–100.
	LossPct  float64
	Sent     int
	Received int
}

// Stats computes the ping metrics of the series.
func (s Series) Stats() Stats {
	st := Stats{Sent: s.Sent, Received: len(s.RTTs), LossPct: 100}
	if s.Sent > 0 {
		st.LossPct = float64(s.Sent-st.Received) / float64(s.Sent) * 100
	}
	if st.Received == 0 {
		return st
	}

	sorted := slices.Clone(s.RTTs)
	slices.Sort(sorted)
	mid := len(sorted) / 2
	if len(sorted)%2 == 1 {
		st.PingMs = ms(sorted[mid])
	} else {
		st.PingMs = (ms(sorted[mid-1]) + ms(sorted[mid])) / 2
	}

	if len(s.RTTs) > 1 {
		var sum time.Duration
		for i := 1; i < len(s.RTTs); i++ {
			sum += (s.RTTs[i] - s.RTTs[i-1]).Abs()
		}
		st.JitterMs = ms(sum) / float64(len(s.RTTs)-1)
	}
	return st
}

func ms(d time.Duration) float64 {
	return float64(d) / float64(time.Millisecond)
}
