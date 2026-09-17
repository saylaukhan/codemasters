// Package scheduler decides when the agent measures: slots of the day from
// the server schedule, a random moment inside each slot and one catch-up
// measurement after the service starts or the computer wakes up (ТЗ п. 2,
// plan.md §4.2).
//
// The schedule is never built into the agent: it comes from
// GET /api/agent/config (ADR-004, T-13). Slot times are local times of the
// schedule time zone, Asia/Almaty (ADR-014).
package scheduler

import (
	"cmp"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"fmt"
	"slices"
	"time"
	_ "time/tzdata" // Windows has no zoneinfo database: embed it for Asia/Almaty.
)

// minSlotLength keeps a slot wide enough for a random moment inside it.
const minSlotLength = time.Minute

// Slot is a measurement window [Start, End) as offsets from local midnight.
type Slot struct {
	Start, End time.Duration
}

// ParseSlot parses a slot in the API form "08:30:00"; seconds may be omitted.
func ParseSlot(start, end string) (Slot, error) {
	s, err := parseClock(start)
	if err != nil {
		return Slot{}, err
	}
	e, err := parseClock(end)
	if err != nil {
		return Slot{}, err
	}
	return Slot{Start: s, End: e}, nil
}

func parseClock(v string) (time.Duration, error) {
	for _, layout := range []string{time.TimeOnly, "15:04"} {
		if t, err := time.Parse(layout, v); err == nil {
			return time.Duration(t.Hour())*time.Hour + time.Duration(t.Minute())*time.Minute +
				time.Duration(t.Second())*time.Second, nil
		}
	}
	return 0, fmt.Errorf("время слота %q: ожидается ЧЧ:ММ:СС", v)
}

func (s Slot) String() string {
	clock := func(d time.Duration) string {
		return fmt.Sprintf("%02d:%02d", int(d/time.Hour), int(d%time.Hour/time.Minute))
	}
	return clock(s.Start) + "–" + clock(s.End)
}

// Schedule is the measurement slots of a day in a time zone, sorted by start.
type Schedule struct {
	Location *time.Location
	Slots    []Slot
}

// NewSchedule loads the time zone and checks the slots: at least one, each
// at least a minute long within a day, none overlapping.
func NewSchedule(timezone string, slots []Slot) (Schedule, error) {
	loc, err := time.LoadLocation(timezone)
	if err != nil {
		return Schedule{}, fmt.Errorf("часовой пояс расписания %q: %w", timezone, err)
	}
	if len(slots) == 0 {
		return Schedule{}, errors.New("расписание без слотов")
	}
	sorted := slices.Clone(slots)
	slices.SortFunc(sorted, func(a, b Slot) int { return cmp.Compare(a.Start, b.Start) })
	for i, s := range sorted {
		if s.Start < 0 || s.End > 24*time.Hour || s.End-s.Start < minSlotLength {
			return Schedule{}, fmt.Errorf("слот %s: конец должен быть позже начала минимум на минуту, в пределах суток", s)
		}
		if i > 0 && s.Start < sorted[i-1].End {
			return Schedule{}, fmt.Errorf("слоты %s и %s пересекаются", sorted[i-1], s)
		}
	}
	return Schedule{Location: loc, Slots: sorted}, nil
}

// window returns slot i on the local date of day.
func (s Schedule) window(day time.Time, i int) (start, end time.Time) {
	y, m, d := day.In(s.Location).Date()
	at := func(off time.Duration) time.Time {
		return time.Date(y, m, d, 0, 0, int(off/time.Second), 0, s.Location)
	}
	return at(s.Slots[i].Start), at(s.Slots[i].End)
}

// Moment returns when the device measures in slot i on the local date of day.
// It differs between devices, days and slots, but is stable for each of them:
// a restart of the service does not move a planned moment.
func (s Schedule) Moment(seed string, day time.Time, i int) time.Time {
	start, end := s.window(day, i)
	span := uint64(end.Sub(start) / time.Second)
	offset := hash("%s|%s|%d", seed, start.Format(time.DateOnly), i) % span
	return start.Add(time.Duration(offset) * time.Second)
}

// hash is a stable pseudo-random number for the formatted key.
func hash(format string, args ...any) uint64 {
	sum := sha256.Sum256(fmt.Appendf(nil, format, args...))
	return binary.BigEndian.Uint64(sum[:8])
}
