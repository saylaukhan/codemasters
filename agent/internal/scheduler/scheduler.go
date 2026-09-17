package scheduler

import (
	"context"
	"log/slog"
	"sync"
	"time"
)

// A catch-up measurement waits a random 1–15 min after the service starts or
// the computer wakes up: the network may not be up yet, and the computers of a
// school switched on together do not measure at once (plan.md §4.2).
const (
	catchUpMin = time.Minute
	catchUpMax = 15 * time.Minute
)

// tick bounds a single wait, so a wake from sleep is noticed within a minute.
const tick = time.Minute

// sleepGap is how much later than planned by the wall clock a wait may end
// before the computer is considered to have slept: timers stop while the OS
// is suspended, the wall clock does not.
const sleepGap = 2 * time.Minute

// Run is a measurement the scheduler starts.
type Run struct {
	At   time.Time
	Slot Slot
	// CatchUp is true when the run was moved to after a service start or a
	// wake from sleep, instead of the planned moment inside the slot.
	CatchUp bool
}

// Options configure a Scheduler.
type Options struct {
	Schedule Schedule
	// Seed spreads the moments of devices apart: the device UID (T-07).
	Seed string
	// Last is when the previous measurement started, from the agent state;
	// zero if the device never measured.
	Last time.Time
	// Measure performs one measurement; the scheduler waits for it to return.
	Measure func(ctx context.Context, run Run)
	Logger  *slog.Logger
	// Now is the clock, time.Now when nil; tests replace it.
	Now func() time.Time
}

// Scheduler starts measurements by the schedule. Only SetSchedule may be
// called from another goroutine; everything else belongs to Run.
type Scheduler struct {
	opts    Options
	catchUp time.Time // earliest measurement after the service start or the last wake
	last    time.Time
	waitEnd time.Time // when the current wait should end by the wall clock
	planned time.Time // the next moment already logged

	mu    sync.Mutex
	sched Schedule
	// changed is set by SetSchedule and taken by step together with the
	// schedule: a new schedule counts as a start of the computer.
	changed bool
	// update tells Run that the schedule changed, so it stops waiting at once.
	update chan struct{}
}

// New creates a scheduler that counts the service as started now.
func New(opts Options) *Scheduler {
	if opts.Now == nil {
		opts.Now = time.Now
	}
	if opts.Logger == nil {
		opts.Logger = slog.Default()
	}
	s := &Scheduler{opts: opts, last: opts.Last, sched: opts.Schedule, update: make(chan struct{}, 1)}
	now := opts.Now()
	if s.last.After(now) {
		s.last = now // the clock went back: do not skip slots until it catches up
	}
	s.start(now)
	return s
}

// Run measures by the schedule until ctx is cancelled.
func (s *Scheduler) Run(ctx context.Context) {
	for {
		timer := time.NewTimer(s.step(ctx))
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-s.update:
			timer.Stop()
		case <-timer.C:
		}
	}
}

// SetSchedule replaces the schedule of the running agent: a schedule changed
// in the admin panel applies without reinstalling the service (ТЗ п. 20,
// T-13). Safe to call from another goroutine; Run picks it up at once, and a
// slot already measured today is not measured again.
func (s *Scheduler) SetSchedule(sched Schedule) {
	s.mu.Lock()
	s.sched = sched
	s.changed = true
	s.mu.Unlock()
	select {
	case s.update <- struct{}{}:
	default: // a change is already pending
	}
}

// schedule returns the schedule in force now and whether it was replaced since
// the previous call; the two are taken together, so a schedule never arrives
// without the change that brought it.
func (s *Scheduler) schedule() (Schedule, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	changed := s.changed
	s.changed = false
	return s.sched, changed
}

// start treats now as a start of the computer: the next measurement is not
// earlier than a random catch-up delay.
func (s *Scheduler) start(now time.Time) {
	span := uint64((catchUpMax-catchUpMin)/time.Second) + 1
	delay := catchUpMin + time.Duration(hash("%s|catch-up|%d", s.opts.Seed, now.Unix())%span)*time.Second
	s.catchUp = now.Add(delay)
}

// step starts the measurement that is due, if any, and returns how long to
// wait before the next step.
func (s *Scheduler) step(ctx context.Context) time.Duration {
	now := s.opts.Now()
	// Round(0) drops the monotonic reading, so Sub compares wall clocks.
	if !s.waitEnd.IsZero() && now.Round(0).Sub(s.waitEnd.Round(0)) > sleepGap {
		s.opts.Logger.Info("выход из сна: замер как после включения ПК", "slept_until", now)
		s.start(now)
	}
	sched, changed := s.schedule()
	if changed {
		// All computers of a school get a new schedule almost at once: a slot
		// it added and already started is measured after a catch-up delay, as
		// after a service start, and not by the whole school at one second
		// (plan.md §4.2). Planned future moments do not move.
		s.opts.Logger.Info("новое расписание: пропущенный слот как после включения ПК")
		s.start(now)
	}
	run, ok := s.next(now, sched)
	if ok && !run.At.After(now) {
		run.At = now
		s.opts.Logger.Info("замер по расписанию", "slot", run.Slot.String(), "catch_up", run.CatchUp)
		s.last = now
		s.opts.Measure(ctx, run)
		now = s.opts.Now()
		run, ok = s.next(now, sched)
	}
	wait := tick
	if ok {
		wait = min(run.At.Sub(now), tick)
		if !run.At.Equal(s.planned) {
			s.planned = run.At
			s.opts.Logger.Info("следующий замер", "at", run.At, "slot", run.Slot.String(), "catch_up", run.CatchUp)
		}
	}
	s.waitEnd = now.Add(wait)
	return wait
}

// next returns the next measurement. A slot counts as done once a measurement
// started at or after its start. Of the slots of today that have begun, only
// the latest can still be measured: earlier missed slots are not caught up.
func (s *Scheduler) next(now time.Time, sched Schedule) (Run, bool) {
	// Every day has a slot, so today and tomorrow always hold one that is not done
	// unless the last measurement is in the future.
	for d := range 2 {
		day := now.In(sched.Location).AddDate(0, 0, d)
		for i, slot := range sched.Slots {
			start, _ := sched.window(day, i)
			if d == 0 && i+1 < len(sched.Slots) {
				if nextStart, _ := sched.window(day, i+1); !nextStart.After(now) {
					continue
				}
			}
			if !s.last.Before(start) {
				continue
			}
			at := sched.Moment(s.opts.Seed, day, i)
			if at.Before(s.catchUp) {
				return Run{At: s.catchUp, Slot: slot, CatchUp: true}, true
			}
			return Run{At: at, Slot: slot}, true
		}
	}
	return Run{}, false
}
