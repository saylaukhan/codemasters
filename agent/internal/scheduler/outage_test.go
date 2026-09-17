package scheduler

import (
	"testing"
	"time"
)

// beat is the heartbeat period of the checks in these tests (plan.md §4.2).
const beat = 5 * time.Minute

var start = time.Date(2026, 9, 17, 9, 0, 0, 0, time.FixedZone("Asia/Almaty", 5*60*60))

// observe runs a series of checks one interval apart, starting at start, and
// returns the outages the tracker closed. A rune 'x' is a failed check, '.' a
// successful one.
func observe(t *OutageTracker, series string) []OutageEvent {
	var closed []OutageEvent
	for i, c := range series {
		event := t.Observe(start.Add(time.Duration(i)*beat), c == '.')
		if event.Closed {
			closed = append(closed, event)
		}
	}
	return closed
}

func TestOutageDurationFromChecks(t *testing.T) {
	tr := &OutageTracker{Interval: beat}
	// Cable out after the first check, back before the last one.
	closed := observe(tr, "..xxx..")
	if len(closed) != 1 {
		t.Fatalf("closed outages = %d, want 1: %+v", len(closed), closed)
	}
	got := closed[0]
	if !got.StartedAt.Equal(start.Add(2*beat)) || !got.EndedAt.Equal(start.Add(5*beat)) {
		t.Fatalf("outage = %v – %v, want the first failed and the first successful check",
			got.StartedAt, got.EndedAt)
	}
	if got.Duration() != 3*beat {
		t.Fatalf("duration = %v, want %v", got.Duration(), 3*beat)
	}
	if _, open := tr.Open(); open {
		t.Fatal("the outage is closed, but the tracker still counts it as open")
	}

	// A single failed check is an outage of one interval, not of nothing.
	if closed = observe(&OutageTracker{Interval: beat}, ".x."); len(closed) != 1 || closed[0].Duration() != beat {
		t.Fatalf("one failed check = %+v, want one outage of %v", closed, beat)
	}
	// The connection never dropped: nothing to send.
	if closed = observe(&OutageTracker{Interval: beat}, "...."); closed != nil {
		t.Fatalf("closed outages with the line up = %+v, want none", closed)
	}
}

func TestOutageEndsAtLastCheckAfterSleep(t *testing.T) {
	tr := &OutageTracker{Interval: beat}
	if event := tr.Observe(start, false); !event.Opened {
		t.Fatalf("first failed check = %+v, want an opened outage", event)
	}
	if event := tr.Observe(start.Add(beat), false); !event.Ongoing {
		t.Fatalf("second failed check = %+v, want an ongoing outage", event)
	}

	// The computer was switched off for three hours and the connection was
	// back when it started: the line was down only until the last check.
	event := tr.Observe(start.Add(3*time.Hour), true)
	if !event.Closed || !event.EndedAt.Equal(start.Add(beat)) {
		t.Fatalf("outage after a sleep = %+v, want it to end at the last failed check %v",
			event, start.Add(beat))
	}
	if event.Duration() != beat {
		t.Fatalf("duration = %v, want %v: a switched off computer is not an outage of the line",
			event.Duration(), beat)
	}
}

func TestOutageSurvivesServiceRestart(t *testing.T) {
	tr := &OutageTracker{Interval: beat}
	observe(tr, "xx")
	open, ok := tr.Open()
	if !ok || !open.Equal(start) {
		t.Fatalf("open outage = %v, %v; want it open since %v", open, ok, start)
	}

	// The service restarts and reads the open outage from the queue; the
	// connection is already back, one interval after the last failed check.
	restarted := &OutageTracker{Interval: beat}
	restarted.Resume(open, start.Add(beat))
	event := restarted.Observe(start.Add(2*beat), true)
	if !event.Closed || !event.StartedAt.Equal(start) || event.Duration() != 2*beat {
		t.Fatalf("outage after a restart = %+v, want %v – %v", event, start, start.Add(2*beat))
	}
}
