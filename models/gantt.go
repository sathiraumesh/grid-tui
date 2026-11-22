package models

import "time"

// Gantt is the reservations of one cluster on a time line: a row per node,
// a column ("cell") per period of time, from now on. A time cursor picks a
// cell; with the selected node it picks a job.
type Gantt struct {
	Detail ClusterDetail // the nodes and their reservations; Detail.Cursor is the selected node
	Zoom   int           // index into GanttZooms
	Col    int           // the time cursor: cells from Origin
}

var _ Model = Gantt{} // Gantt implements Model

// GanttZooms are how long one cell lasts, from the closest to the widest.
var GanttZooms = []time.Duration{
	15 * time.Minute, 30 * time.Minute, time.Hour, 2 * time.Hour, 4 * time.Hour, 12 * time.Hour,
}

// GanttSpan is how far ahead the time line goes.
const GanttSpan = 7 * 24 * time.Hour

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

// Cell is how long one cell lasts at the current zoom.
func (g Gantt) Cell() time.Duration { return GanttZooms[g.Zoom] }

// Origin is when the first cell starts: the start of the cell holding now,
// counted from midnight so the cells fall on round hours.
func (g Gantt) Origin() time.Time {
	at := g.Detail.At
	midnight := time.Date(at.Year(), at.Month(), at.Day(), 0, 0, 0, 0, at.Location())
	cells := at.Sub(midnight) / g.Cell()
	return midnight.Add(cells * g.Cell())
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

// Now puts the time cursor back on now.
func (g Gantt) Now() Gantt {
	g.Col = 0
	return g
}

// ZoomBy changes how long a cell lasts (positive: wider), keeping the
// cursor at about the same time.
func (g Gantt) ZoomBy(step int) Gantt {
	at := g.CursorTime()
	g.Zoom = max(min(g.Zoom+step, len(GanttZooms)-1), 0)
	g.Col = int(at.Sub(g.Origin()) / g.Cell())
	return g.MoveTime(0)
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
	from = g.Detail.At
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
