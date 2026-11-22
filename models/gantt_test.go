package models

import (
	"testing"
	"time"
)

// ganttNodes, at t0 = 14:30: gros-1 runs job 1 13:30→16:30 then job 2 on
// gros-1 and gros-2 18:00→20:00; gros-2 has a besteffort job now; gros-3 is dead.
func sampleGantt() Gantt {
	at := func(h, m int) time.Time { return time.Date(2026, 11, 22, h, m, 0, 0, time.Local) }
	nodes := []NodeStatus{
		{Name: "gros-1", Hard: "alive", Reservations: []Reservation{
			{JobID: 1, User: "bob", Queue: "default", Start: at(13, 30), End: at(16, 30)},
			{JobID: 2, User: "eve", Queue: "default", Start: at(18, 0), End: at(20, 0)},
		}},
		{Name: "gros-2", Hard: "alive", Reservations: []Reservation{
			{JobID: 3, Queue: "besteffort", Start: at(14, 0), End: at(15, 0)},
			{JobID: 2, User: "eve", Queue: "default", Start: at(18, 0), End: at(20, 0)},
		}},
		{Name: "gros-3", Hard: "dead"},
	}
	return NewGantt(NewClusterDetail("nancy", Cluster{UID: "gros"}).WithNodes(nodes, t0))
}

func TestGanttOriginAndCells(t *testing.T) {
	g := sampleGantt()
	if want := time.Date(2026, 11, 22, 14, 0, 0, 0, time.Local); !g.Origin().Equal(want) {
		t.Errorf("Origin = %v, want %v", g.Origin(), want)
	}
	if g.MaxCol() != 6*7*24-1 {
		t.Errorf("MaxCol = %d", g.MaxCol())
	}
	g = g.ZoomBy(-2) // 15 min
	if want := time.Date(2026, 11, 22, 14, 30, 0, 0, time.Local); !g.Origin().Equal(want) {
		t.Errorf("15 min Origin = %v, want %v", g.Origin(), want)
	}
}

func TestGanttJobIn(t *testing.T) {
	g := sampleGantt()
	g1, g2 := g.Detail.Nodes[0], g.Detail.Nodes[1]
	cases := []struct {
		node NodeStatus
		col  int // 0 = 14:00
		job  int64
		ok   bool
	}{
		{g1, 0, 1, true},  // 14:00-15:00 job 1
		{g1, 2, 1, true},  // 16:00-17:00: job 1 until 16:30
		{g1, 3, 0, false}, // 17:00-18:00 free
		{g1, 4, 2, true},
		{g2, 0, 3, true}, // only the besteffort job
		{g2, 1, 0, false},
	}
	for _, c := range cases {
		r, ok := g.JobIn(c.node, c.col)
		if ok != c.ok || r.JobID != c.job {
			t.Errorf("%s col %d: job %d %v, want %d %v", c.node.Name, c.col, r.JobID, ok, c.job, c.ok)
		}
	}
}

func TestGanttFreeIn(t *testing.T) {
	g := sampleGantt()
	if free, usable := g.FreeIn(0); free != 1 || usable != 2 { // gros-2's besteffort counts as free
		t.Errorf("14:00: free %d of %d", free, usable)
	}
	if free, _ := g.FreeIn(4); free != 0 {
		t.Errorf("18:00: free %d", free)
	}
	if free, _ := g.FreeIn(3); free != 2 {
		t.Errorf("17:00: free %d", free)
	}
}

func TestGanttJumpJob(t *testing.T) {
	g := sampleGantt() // gros-1, cursor on job 1
	if g = g.JumpJob(1); g.Col != 4 {
		t.Fatalf("next job: Col = %d, want 4 (18:00)", g.Col)
	}
	if g = g.JumpJob(1); g.Col != 4 {
		t.Errorf("no job after: Col = %d, want to stay at 4", g.Col)
	}
	if g = g.MoveTime(1).JumpJob(-1); g.Col != 0 {
		t.Errorf("previous job: Col = %d, want 0 (job 1's first cell)", g.Col)
	}
}

func TestGanttZoomKeepsTheTime(t *testing.T) {
	g := sampleGantt().MoveTime(4) // 18:00
	if g = g.ZoomBy(-1); !g.CursorTime().Equal(time.Date(2026, 11, 22, 18, 0, 0, 0, time.Local)) {
		t.Errorf("30 min: cursor at %v", g.CursorTime())
	}
	if g = g.ZoomBy(100); g.Zoom != len(GanttZooms)-1 {
		t.Errorf("zoom is capped: %d", g.Zoom)
	}
	if g = g.MoveTime(10000); g.Col != g.MaxCol() {
		t.Errorf("time cursor is capped: %d", g.Col)
	}
	if g = g.ToNow(); g.Col != 0 {
		t.Errorf("ToNow: %d", g.Col)
	}
}

func TestGanttSelectedAndJobNodes(t *testing.T) {
	g := sampleGantt().MoveTime(4)
	n, r, ok := g.Selected()
	if !ok || n.Name != "gros-1" || r.JobID != 2 || g.JobNodes(2) != 2 {
		t.Errorf("selected %s job %d (%v), job 2 on %d nodes", n.Name, r.JobID, ok, g.JobNodes(2))
	}
}

func TestGanttFreeSpan(t *testing.T) {
	g := sampleGantt().MoveTime(3) // 17:00, gros-1 free between its jobs
	from, to := g.FreeSpan(g.Detail.Nodes[0])
	at := func(h, m int) time.Time { return time.Date(2026, 11, 22, h, m, 0, 0, time.Local) }
	if !from.Equal(at(16, 30)) || !to.Equal(at(18, 0)) {
		t.Errorf("free %v → %v", from, to)
	}
}

func TestGanttWithDetailKeepsTheCursors(t *testing.T) {
	g := sampleGantt().Move(1).MoveTime(5).ZoomBy(1)
	h := g.WithDetail(g.Detail)
	if h.Detail.Cursor != 1 || h.Col != g.Col || h.Zoom != g.Zoom {
		t.Errorf("cursors lost: %+v", h)
	}
}

func TestGanttModesKeepTheTime(t *testing.T) {
	g := sampleGantt().MoveTime(4) // 18:00
	w := g.WithMode(ModeWeek)
	if want := time.Date(2026, 11, 22, 18, 0, 0, 0, time.Local); !w.Day.Equal(want) {
		t.Errorf("week slot = %v, want %v", w.Day, want)
	}
	m := w.WithMode(ModeMonth)
	if want := time.Date(2026, 11, 22, 0, 0, 0, 0, time.Local); !m.Day.Equal(want) {
		t.Errorf("month day = %v, want %v", m.Day, want)
	}
	back := w.MoveDay(1, 1).WithMode(ModeTimeline) // Mon 23 20:00
	if want := time.Date(2026, 11, 23, 20, 0, 0, 0, time.Local); !back.CursorTime().Equal(want) {
		t.Errorf("back on the time line at %v, want %v", back.CursorTime(), want)
	}
	if ModeWeek.String() != "week" {
		t.Error(ModeWeek.String())
	}
}

func TestGanttMoveDayStaysInTheShownTime(t *testing.T) {
	w := sampleGantt().WithMode(ModeWeek)
	if w = w.MoveDay(0, -5); !w.Day.Equal(time.Date(2026, 11, 22, 14, 0, 0, 0, time.Local)) {
		t.Errorf("not before now's slot: %v", w.Day)
	}
	if w = w.MoveDay(1000, 0); w.Day.After(w.End()) {
		t.Errorf("not after the end: %v", w.Day)
	}
	m := sampleGantt().WithMode(ModeMonth).MoveDay(-3, 0)
	if !m.Day.Equal(time.Date(2026, 11, 22, 0, 0, 0, 0, time.Local)) {
		t.Errorf("month: not before today: %v", m.Day)
	}
}

func TestGanttFreeBetweenAndDayFree(t *testing.T) {
	g := sampleGantt() // 2 usable nodes
	at := func(h int) time.Time { return time.Date(2026, 11, 22, h, 0, 0, 0, time.Local) }
	if free, usable := g.FreeBetween(at(16), at(18)); free != 1 || usable != 2 { // gros-1 busy until 16:30
		t.Errorf("16-18: %d of %d", free, usable)
	}
	if free, _ := g.FreeBetween(at(18), at(20)); free != 0 {
		t.Errorf("18-20: %d", free)
	}
	least, most, usable := g.DayFree(at(0))
	if least != 0 || most != 2 || usable != 2 {
		t.Errorf("today: %d-%d of %d", least, most, usable)
	}
	if least, most, _ := g.DayFree(at(0).AddDate(0, 0, 1)); least != 2 || most != 2 {
		t.Errorf("tomorrow: %d-%d", least, most)
	}
}

func TestGanttJobsStartingAndDuring(t *testing.T) {
	g := sampleGantt()
	at := func(h int) time.Time { return time.Date(2026, 11, 22, h, 0, 0, 0, time.Local) }
	if n := g.JobsStarting(at(0), at(24)); n != 2 { // jobs 1 and 2 (3 is besteffort)
		t.Errorf("starting today: %d", n)
	}
	if n := g.JobsDuring(at(16), at(19)); n != 2 {
		t.Errorf("during 16-19: %d", n)
	}
}

func TestGanttClock(t *testing.T) {
	g := sampleGantt() // loaded at 14:30, cells from 14:00
	if !g.Now().Equal(t0) || g.NowCol() != 0 {
		t.Fatalf("before a tick, now is the load: %v col %d", g.Now(), g.NowCol())
	}
	g = g.WithClock(t0.Add(2*time.Hour + 10*time.Minute)) // 16:40
	if g.NowCol() != 2 || !g.Origin().Equal(time.Date(2026, 11, 22, 14, 0, 0, 0, time.Local)) {
		t.Errorf("the now mark moves, the cells don't: col %d origin %v", g.NowCol(), g.Origin())
	}
	if g = g.ToNow(); g.Col != 2 {
		t.Errorf("ToNow goes to the clock's cell: %d", g.Col)
	}
	if w := g.WithMode(ModeWeek).ToNow(); !w.Day.Equal(time.Date(2026, 11, 22, 16, 0, 0, 0, time.Local)) {
		t.Errorf("week ToNow: %v", w.Day)
	}
	if g.WithClock(t0.Add(-time.Hour)).Now() != t0 {
		t.Error("a clock before the load is ignored")
	}
}
