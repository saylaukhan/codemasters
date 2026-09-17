package scheduler

import "time"

// sleepIntervals is how many check intervals may pass between the last failed
// check and a successful one before the computer counts as switched off or
// asleep: a switched off computer is not an outage of the line (ТЗ п. 2).
const sleepIntervals = 2

// OutageEvent is what one connectivity check changed. Exactly one of Opened,
// Ongoing and Closed is true; an empty event means the connection was up and
// stayed up.
type OutageEvent struct {
	// Opened is the first failed check: the outage starts at StartedAt.
	Opened bool
	// Ongoing is a failed check inside an outage that is already open.
	Ongoing bool
	// Closed is the first successful check after an outage: it is finished
	// and goes to POST /api/outages.
	Closed    bool
	StartedAt time.Time
	EndedAt   time.Time
}

// Duration is how long a closed outage lasted.
func (e OutageEvent) Duration() time.Duration {
	return e.EndedAt.Sub(e.StartedAt)
}

// OutageTracker turns a series of connectivity checks (the heartbeat, T-12)
// into outages: the start is the first failed check, the end is the first
// successful one. It keeps no clock of its own and is not safe for concurrent
// use.
type OutageTracker struct {
	// Interval is the period between checks, so a long silence can be told
	// from a real outage; zero switches that rule off. It comes from the
	// server configuration (ADR-004), never from the code.
	Interval time.Duration

	started    time.Time
	lastFailed time.Time
}

// Resume restores an outage that was still open when the service stopped: it
// is read from the queue on start, so a restart does not lose the outage.
func (t *OutageTracker) Resume(startedAt, lastFailedAt time.Time) {
	if startedAt.IsZero() {
		return
	}
	t.started = startedAt
	t.lastFailed = lastFailedAt
	if t.lastFailed.Before(startedAt) {
		t.lastFailed = startedAt
	}
}

// Open returns the start of the outage that is going on now.
func (t *OutageTracker) Open() (time.Time, bool) {
	return t.started, !t.started.IsZero()
}

// Observe records one check made at the moment at: ok is false only when the
// server did not answer at all (a network error or a timeout); an error
// answer of the server means the connection is there.
func (t *OutageTracker) Observe(at time.Time, ok bool) OutageEvent {
	if !ok {
		if t.started.IsZero() {
			t.started, t.lastFailed = at, at
			return OutageEvent{Opened: true, StartedAt: at}
		}
		if at.After(t.lastFailed) {
			t.lastFailed = at
		}
		return OutageEvent{Ongoing: true, StartedAt: t.started}
	}
	if t.started.IsZero() {
		return OutageEvent{}
	}

	ended := at
	// More than sleepIntervals without any check: the computer was off or
	// asleep, so the line counts as down only until the last failed check.
	if t.Interval > 0 && at.Sub(t.lastFailed) > sleepIntervals*t.Interval {
		ended = t.lastFailed
	}
	if ended.Before(t.started) {
		ended = t.started
	}
	event := OutageEvent{Closed: true, StartedAt: t.started, EndedAt: ended}
	t.started, t.lastFailed = time.Time{}, time.Time{}
	return event
}
