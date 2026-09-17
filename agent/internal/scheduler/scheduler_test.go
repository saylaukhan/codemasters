package scheduler

import (
	"context"
	"io"
	"log/slog"
	"strings"
	"testing"
	"time"
)

// testSchedule is the default schedule of docs/tasks/README.md; the agent
// itself gets it from the server.
func testSchedule(t *testing.T) Schedule {
	t.Helper()
	var slots []Slot
	for _, s := range [][2]string{{"13:30:00", "14:00:00"}, {"08:30", "09:00"}, {"11:00", "11:30"}, {"16:00", "16:30"}} {
		slot, err := ParseSlot(s[0], s[1])
		if err != nil {
			t.Fatalf("ParseSlot(%q, %q): %v", s[0], s[1], err)
		}
		slots = append(slots, slot)
	}
	sched, err := NewSchedule("Asia/Almaty", slots)
	if err != nil {
		t.Fatalf("NewSchedule: %v", err)
	}
	return sched
}

func almaty(t *testing.T, sched Schedule, v string) time.Time {
	t.Helper()
	at, err := time.ParseInLocation("2006-01-02 15:04:05", v, sched.Location)
	if err != nil {
		t.Fatalf("time %q: %v", v, err)
	}
	return at
}

// device is a scheduler on a fake clock that records its measurements; each
// measurement takes 40 s of the fake time.
type device struct {
	clock time.Time
	runs  []Run
	s     *Scheduler
}

func startDevice(sched Schedule, seed string, last, now time.Time) *device {
	d := &device{clock: now}
	d.s = New(Options{
		Schedule: sched,
		Seed:     seed,
		Last:     last,
		Logger:   slog.New(slog.NewTextHandler(io.Discard, nil)),
		Now:      func() time.Time { return d.clock },
		Measure: func(_ context.Context, run Run) {
			d.runs = append(d.runs, run)
			d.clock = d.clock.Add(40 * time.Second)
		},
	})
	return d
}

// runUntil steps the scheduler, moving the clock by each returned wait.
func (d *device) runUntil(until time.Time) {
	for d.clock.Before(until) {
		d.clock = d.clock.Add(d.s.step(context.Background()))
	}
}

func TestNewScheduleErrors(t *testing.T) {
	slot := func(start, end string) Slot {
		s, err := ParseSlot(start, end)
		if err != nil {
			t.Fatalf("ParseSlot: %v", err)
		}
		return s
	}
	cases := map[string]struct {
		tz    string
		slots []Slot
		want  string
	}{
		"unknown zone":  {"Asia/Nowhere", []Slot{slot("08:30", "09:00")}, "часовой пояс"},
		"no slots":      {"Asia/Almaty", nil, "без слотов"},
		"end before":    {"Asia/Almaty", []Slot{slot("09:00", "08:30")}, "позже начала"},
		"too short":     {"Asia/Almaty", []Slot{slot("09:00:00", "09:00:30")}, "позже начала"},
		"overlapping":   {"Asia/Almaty", []Slot{slot("11:00", "11:30"), slot("08:30", "11:15")}, "пересекаются"},
		"past midnight": {"Asia/Almaty", []Slot{{Start: 23 * time.Hour, End: 25 * time.Hour}}, "в пределах суток"},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			_, err := NewSchedule(tc.tz, tc.slots)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("NewSchedule: err = %v, want %q", err, tc.want)
			}
		})
	}
	if _, err := ParseSlot("8.30", "09:00"); err == nil {
		t.Fatal("ParseSlot(8.30): want error")
	}
}

func TestMomentInsideSlotAndDiffersBetweenDevices(t *testing.T) {
	sched := testSchedule(t)
	day := almaty(t, sched, "2026-09-01 00:00:00")
	for n := range 60 {
		day := day.AddDate(0, 0, n)
		for i := range sched.Slots {
			start, end := sched.window(day, i)
			a := sched.Moment("device-a", day, i)
			b := sched.Moment("device-b", day, i)
			for _, m := range []time.Time{a, b} {
				if m.Before(start) || !m.Before(end) {
					t.Fatalf("%s slot %s: moment %s outside [%s, %s)", day.Format(time.DateOnly), sched.Slots[i], m, start, end)
				}
			}
			if a.Equal(b) {
				t.Errorf("%s slot %s: devices a and b share moment %s", day.Format(time.DateOnly), sched.Slots[i], a)
			}
			if again := sched.Moment("device-a", day, i); !again.Equal(a) {
				t.Errorf("moment of device a moved on recompute: %s, then %s", a, again)
			}
		}
	}
}

func TestMeasuresEverySlotOnceADay(t *testing.T) {
	sched := testSchedule(t)
	start := almaty(t, sched, "2026-09-17 07:00:00")
	d := startDevice(sched, "device-a", start.AddDate(0, 0, -1), start)
	d.runUntil(start.AddDate(0, 0, 1))

	if len(d.runs) != len(sched.Slots) {
		t.Fatalf("runs = %d, want %d: %+v", len(d.runs), len(sched.Slots), d.runs)
	}
	for i, run := range d.runs {
		want := sched.Moment("device-a", start, i)
		if !run.At.Equal(want) || run.CatchUp {
			t.Errorf("run %d = %s catch-up %v, want planned %s", i, run.At, run.CatchUp, want)
		}
	}
}

func TestRestartInsideMissedSlotCatchesUpOnce(t *testing.T) {
	sched := testSchedule(t)
	morning := almaty(t, sched, "2026-09-17 07:00:00")
	planned := sched.Moment("device-a", morning, 0)
	_, slotEnd := sched.window(morning, 0)
	yesterday := morning.Add(-10 * time.Hour)

	for name, restart := range map[string]time.Time{
		"inside the slot":   planned.Add(30 * time.Second),
		"after the slot":    almaty(t, sched, "2026-09-17 10:00:00"),
		"after three slots": almaty(t, sched, "2026-09-17 15:00:00"),
	} {
		t.Run(name, func(t *testing.T) {
			if name == "inside the slot" && !restart.Before(slotEnd) {
				t.Fatalf("planned moment %s is at the slot end; pick another seed", planned)
			}
			// The computer was off at the planned moment; the service starts at restart.
			d := startDevice(sched, "device-a", yesterday, restart)
			var nextSlot time.Time
			for i := range sched.Slots {
				if begin, _ := sched.window(restart, i); begin.After(restart) {
					nextSlot = begin
					break
				}
			}
			d.runUntil(nextSlot)

			if len(d.runs) != 1 || !d.runs[0].CatchUp {
				t.Fatalf("runs before %s = %+v, want one catch-up", nextSlot, d.runs)
			}
			if at := d.runs[0].At; at.Before(restart.Add(catchUpMin)) || at.After(restart.Add(catchUpMax)) {
				t.Fatalf("catch-up at %s, want 1–15 min after %s", at, restart)
			}

			// Another restart after the catch-up does not measure the slot again.
			again := startDevice(sched, "device-a", d.runs[0].At, d.runs[0].At.Add(2*time.Minute))
			again.runUntil(nextSlot)
			if len(again.runs) != 0 {
				t.Fatalf("runs after second restart = %+v, want none", again.runs)
			}
		})
	}
}

func TestWakeFromSleepActsAsStart(t *testing.T) {
	sched := testSchedule(t)
	morning := almaty(t, sched, "2026-09-17 07:00:00")
	d := startDevice(sched, "device-a", morning.Add(-10*time.Hour), morning)
	d.runUntil(almaty(t, sched, "2026-09-17 08:10:00"))

	// The computer sleeps through the 08:30 and 11:00 slots: the clock jumps
	// while the scheduler waits.
	wake := almaty(t, sched, "2026-09-17 12:00:00")
	d.clock = wake
	d.runUntil(almaty(t, sched, "2026-09-17 13:30:00"))

	if len(d.runs) != 1 || !d.runs[0].CatchUp {
		t.Fatalf("runs after wake = %+v, want one catch-up", d.runs)
	}
	if at := d.runs[0].At; at.Before(wake.Add(catchUpMin)) || at.After(wake.Add(catchUpMax)) {
		t.Fatalf("catch-up at %s, want 1–15 min after wake %s", at, wake)
	}
}

func TestRunStopsOnCancel(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	done := make(chan struct{})
	go func() {
		defer close(done)
		New(Options{
			Schedule: testSchedule(t),
			Seed:     "device-a",
			Logger:   slog.New(slog.NewTextHandler(io.Discard, nil)),
			Measure:  func(context.Context, Run) {},
		}).Run(ctx)
	}()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("Run did not return after cancel")
	}
}

// TestSetScheduleAppliesWithoutRestart: a schedule changed in the admin panel
// is picked up by the running scheduler; slots already measured today are not
// measured again and no extra catch-up appears (T-13).
func TestSetScheduleAppliesWithoutRestart(t *testing.T) {
	sched := testSchedule(t)
	start := almaty(t, sched, "2026-09-17 07:00:00")
	d := startDevice(sched, "device-a", start.AddDate(0, 0, -1), start)
	d.runUntil(almaty(t, sched, "2026-09-17 12:00:00"))
	if len(d.runs) != 2 {
		t.Fatalf("runs before the change = %+v, want the 08:30 and 11:00 slots", d.runs)
	}

	changed, err := NewSchedule("Asia/Almaty", []Slot{{Start: 14 * time.Hour, End: 14*time.Hour + 30*time.Minute},
		{Start: 18 * time.Hour, End: 18*time.Hour + 30*time.Minute}})
	if err != nil {
		t.Fatalf("NewSchedule: %v", err)
	}
	d.s.SetSchedule(changed)

	// Nothing is measured just because the schedule changed.
	d.runUntil(almaty(t, sched, "2026-09-17 13:00:00"))
	if len(d.runs) != 2 {
		t.Fatalf("runs right after the change = %+v, want no extra measurement", d.runs)
	}

	d.runUntil(almaty(t, sched, "2026-09-18 00:00:00"))
	rest := d.runs[2:]
	if len(rest) != len(changed.Slots) {
		t.Fatalf("runs by the new schedule = %d, want %d: %+v", len(rest), len(changed.Slots), rest)
	}
	for i, run := range rest {
		want := changed.Moment("device-a", start, i)
		if !run.At.Equal(want) || run.CatchUp {
			t.Errorf("run %d = %s catch-up %v, want planned %s in slot %s", i, run.At, run.CatchUp, want, changed.Slots[i])
		}
	}
}
