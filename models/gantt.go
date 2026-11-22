package models

import "time"

// Gantt is the reservations of one cluster, seen three ways (Mode):
//
//   - a time line: a row per node, a column ("cell") per period of time,
//     from now on. A time cursor (Col) picks a cell; with the selected
//     node it picks a job.
//   - a week: a column per day, a row per WeekSlot; each slot says how
//     many nodes are free all through it.
//   - a month: a calendar of days; each says how many nodes are free at
//     its worst and best moments, and how many jobs start.
//
// The week and the month have their own cursor (Day), a time.
type Gantt struct {
	Detail ClusterDetail // the nodes and their reservations; Detail.Cursor is the selected node
	Mode   GanttMode
	Zoom   int       // index into GanttZooms (time line)
	Col    int       // the time line's cursor: cells from Origin
	Day    time.Time // the week's and the month's cursor: the start of a slot (week) or a day (month)
	Clock  time.Time // the time now, kept up to date without loading again; zero: Detail.At
}

// GanttMode is how the reservations are shown.
type GanttMode int

const (
	ModeTimeline GanttMode = iota
	ModeWeek
	ModeMonth
)

// String is the mode's name, for the screen.
func (m GanttMode) String() string {
	return [...]string{"timeline", "week", "month"}[m]
}

// WeekSlot is how long one row of the week lasts.
const WeekSlot = 2 * time.Hour

var _ Model = Gantt{} // Gantt implements Model

// GanttZooms are how long one cell lasts, from the closest to the widest.
var GanttZooms = []time.Duration{
	15 * time.Minute, 30 * time.Minute, time.Hour, 2 * time.Hour, 4 * time.Hour, 12 * time.Hour,
}

// GanttSpan is how far ahead the reservations are shown: six weeks, so a
// month view has something to show.
const GanttSpan = 6 * 7 * 24 * time.Hour

const defaultZoom = 2 // 1 hour per cell

// NewGantt makes the time line of a cluster's detail, at 1 hour per cell,
// the cursor on now.
func NewGantt(d ClusterDetail) Gantt {
	return Gantt{Detail: d, Zoom: defaultZoom}
}

// WithDetail stores reloaded nodes, keeping the zoom and the cursors.
func (g Gantt) WithDetail(d ClusterDetail) Gantt {
	d.Cursor = g.Detail.Cursor
	g.Detail = d.Move(0)
	return g.MoveTime(0)
}

// Len is how many nodes there are.
func (g Gantt) Len() int { return g.Detail.Len() }

// Now is the time now: the clock if it has ticked since the load, else
// when the data was loaded. The cells stay where the load put them; the
// now marks move as the clock goes.
func (g Gantt) Now() time.Time {
	if g.Clock.After(g.Detail.At) {
		return g.Clock
	}
	return g.Detail.At
}

// WithClock sets the time now.
func (g Gantt) WithClock(t time.Time) Gantt {
	g.Clock = t
	return g
}

// NowCol is the cell holding the time now.
func (g Gantt) NowCol() int { return int(g.Now().Sub(g.Origin()) / g.Cell()) }

// End is when the shown time ends: GanttSpan after the load.
func (g Gantt) End() time.Time { return g.Detail.At.Add(GanttSpan) }

// WithMode shows the reservations another way, the cursor kept at about
// the same time: the time line's cursor becomes the week's slot or the
// month's day, and back.
func (g Gantt) WithMode(m GanttMode) Gantt {
	at := g.CursorTime()
	if g.Mode != ModeTimeline {
		at = g.cursorDay()
	}
	g.Mode = m
	switch m {
	case ModeTimeline:
		g.Col = int(maxTime(at, g.Origin()).Sub(g.Origin()) / g.Cell())
		return g.MoveTime(0)
	case ModeWeek:
		g.Day = slotStart(at, WeekSlot)
	case ModeMonth:
		g.Day = midnight(at)
	}
	return g
}

// cursorDay is the week's or the month's cursor, now if it isn't set.
func (g Gantt) cursorDay() time.Time {
	if g.Day.IsZero() {
		return g.Now()
	}
	return g.Day
}

// MoveDay moves the week's or the month's cursor by days and, in the week,
// slots (each WeekSlot long), within the shown time: from today's first
// slot (or day) to the last one.
func (g Gantt) MoveDay(days, slots int) Gantt {
	at := g.cursorDay().AddDate(0, 0, days).Add(time.Duration(slots) * WeekSlot)
	first, last := slotStart(g.Now(), WeekSlot), slotStart(g.End(), WeekSlot)
	if g.Mode == ModeMonth {
		at, first, last = midnight(at), midnight(g.Now()), midnight(g.End())
	}
	if at.Before(first) {
		at = first
	}
	if at.After(last) {
		at = last
	}
	g.Day = at
	return g
}

// FreeBetween counts the usable nodes, and those with no regular job at
// any time in [from, to): the nodes one could have for all of it.
func (g Gantt) FreeBetween(from, to time.Time) (free, usable int) {
	for _, n := range g.Detail.Nodes {
		switch n.SlotAt(from, to) {
		case SlotDown:
			continue
		case SlotFree, SlotBestEffort:
			free++
		}
		usable++
	}
	return free, usable
}

// DayFree is the fewest and the most nodes free during the day starting at
// day (counted hour by hour, from now on), and the usable nodes.
func (g Gantt) DayFree(day time.Time) (least, most, usable int) {
	least = -1
	end := day.AddDate(0, 0, 1)
	for t := maxTime(day, slotStart(g.Now(), time.Hour)); t.Before(end) && t.Before(g.End()); t = t.Add(time.Hour) {
		free, u := g.FreeBetween(t, t.Add(time.Hour))
		usable = u
		if least < 0 || free < least {
			least = free
		}
		most = max(most, free)
	}
	return max(least, 0), most, usable
}

// JobsStarting counts the regular jobs that start in [from, to).
func (g Gantt) JobsStarting(from, to time.Time) int {
	seen := map[int64]bool{}
	for _, n := range g.Detail.Nodes {
		for _, r := range n.Reservations {
			if !r.BestEffort() && !r.Start.Before(from) && r.Start.Before(to) {
				seen[r.JobID] = true
			}
		}
	}
	return len(seen)
}

// JobsDuring counts the regular jobs that hold a node at some time in [from, to).
func (g Gantt) JobsDuring(from, to time.Time) int {
	seen := map[int64]bool{}
	for _, n := range g.Detail.Nodes {
		for _, r := range n.Reservations {
			if !r.BestEffort() && r.Start.Before(to) && r.End.After(from) {
				seen[r.JobID] = true
			}
		}
	}
	return len(seen)
}

// midnight is the start of t's day.
func midnight(t time.Time) time.Time {
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, t.Location())
}

// slotStart is the start of the slot of t, slots counted from midnight.
func slotStart(t time.Time, slot time.Duration) time.Time {
	m := midnight(t)
	return m.Add(t.Sub(m) / slot * slot)
}

// Cell is how long one cell lasts at the current zoom.
func (g Gantt) Cell() time.Duration { return GanttZooms[g.Zoom] }

// Origin is when the first cell starts: the start of the cell holding now,
// counted from midnight so the cells fall on round hours.
func (g Gantt) Origin() time.Time {
	return slotStart(g.Detail.At, g.Cell())
}

// CellStart is when cell col starts.
func (g Gantt) CellStart(col int) time.Time {
	return g.Origin().Add(time.Duration(col) * g.Cell())
}

// MaxCol is the last cell of the time line.
func (g Gantt) MaxCol() int { return int(GanttSpan/g.Cell()) - 1 }

// CursorTime is when the cell under the time cursor starts.
func (g Gantt) CursorTime() time.Time { return g.CellStart(g.Col) }

// Move moves the selected node by step.
func (g Gantt) Move(step int) Gantt {
	g.Detail = g.Detail.Move(step)
	return g
}

// MoveTime moves the time cursor by step cells, within the time line.
func (g Gantt) MoveTime(step int) Gantt {
	g.Col = max(min(g.Col+step, g.MaxCol()), 0)
	return g
}

// ToNow puts the cursor back on the time now.
func (g Gantt) ToNow() Gantt {
	g.Col = 0
	g.Day = time.Time{}
	if g.Mode == ModeTimeline {
		return g.MoveTime(g.NowCol())
	}
	return g.WithMode(g.Mode) // the slot or the day of now
}

// ZoomBy changes how long a cell lasts (positive: wider), keeping the
// cursor at about the same time.
func (g Gantt) ZoomBy(step int) Gantt {
	at := g.CursorTime()
	g.Zoom = max(min(g.Zoom+step, len(GanttZooms)-1), 0)
	g.Col = int(at.Sub(g.Origin()) / g.Cell())
	return g.MoveTime(0)
}

// ZoomTo sets the zoom to GanttZooms[i] (the week and the month use it
// before opening the time line at their cursor).
func (g Gantt) ZoomTo(i int) Gantt {
	g.Zoom = max(min(i, len(GanttZooms)-1), 0)
	return g
}

// SlotIn is what node n does during cell col.
func (g Gantt) SlotIn(n NodeStatus, col int) Slot {
	start := g.CellStart(col)
	return n.SlotAt(start, start.Add(g.Cell()))
}

// JobIn is the job of node n in cell col: the regular job overlapping it
// the most, else a besteffort one.
func (g Gantt) JobIn(n NodeStatus, col int) (Reservation, bool) {
	start := g.CellStart(col)
	end := start.Add(g.Cell())
	var best Reservation
	var bestTime time.Duration
	found := false
	for _, r := range n.Reservations {
		overlap := minTime(r.End, end).Sub(maxTime(r.Start, start))
		if overlap <= 0 {
			continue
		}
		if r.BestEffort() {
			overlap /= 1000 // a regular job wins over a besteffort one
		}
		if !found || overlap > bestTime {
			best, bestTime, found = r, overlap, true
		}
	}
	return best, found
}

// Selected is the node selected, and its job under the time cursor if any.
func (g Gantt) Selected() (NodeStatus, Reservation, bool) {
	n, ok := g.Detail.Selected()
	if !ok {
		return NodeStatus{}, Reservation{}, false
	}
	r, has := g.JobIn(n, g.Col)
	return n, r, has
}

// JumpJob moves the time cursor to the start of the next (step > 0) or
// previous (step < 0) job of the selected node.
func (g Gantt) JumpJob(step int) Gantt {
	n, ok := g.Detail.Selected()
	if !ok {
		return g
	}
	cur, onJob := g.JobIn(n, g.Col)
	for col := g.Col + step; col >= 0 && col <= g.MaxCol(); col += step {
		r, has := g.JobIn(n, col)
		if !has || (onJob && r.JobID == cur.JobID) {
			continue
		}
		if step < 0 { // go to that job's first cell
			for col > 0 {
				if prev, ok := g.JobIn(n, col-1); !ok || prev.JobID != r.JobID {
					break
				}
				col--
			}
		}
		g.Col = col
		return g
	}
	return g
}

// FreeIn counts the usable nodes, and those with no regular job, in cell col.
func (g Gantt) FreeIn(col int) (free, usable int) {
	for _, n := range g.Detail.Nodes {
		switch g.SlotIn(n, col) {
		case SlotDown:
			continue
		case SlotFree, SlotBestEffort:
			free++
		}
		usable++
	}
	return free, usable
}

// JobNodes is how many nodes job id holds.
func (g Gantt) JobNodes(id int64) int {
	count := 0
	for _, n := range g.Detail.Nodes {
		for _, r := range n.Reservations {
			if r.JobID == id {
				count++
				break
			}
		}
	}
	return count
}

// FreeSpan is the free time around the time cursor on node n: from the end
// of the job before it (or now) to the start of the next (zero: none known).
func (g Gantt) FreeSpan(n NodeStatus) (from, to time.Time) {
	at := g.CursorTime()
	from = g.Now()
	for _, r := range n.Reservations {
		if r.BestEffort() {
			continue
		}
		if !r.End.After(at) && r.End.After(from) {
			from = r.End
		}
		if r.Start.After(at) && (to.IsZero() || r.Start.Before(to)) {
			to = r.Start
		}
	}
	return from, to
}

func minTime(a, b time.Time) time.Time {
	if a.Before(b) {
		return a
	}
	return b
}

func maxTime(a, b time.Time) time.Time {
	if a.After(b) {
		return a
	}
	return b
}
