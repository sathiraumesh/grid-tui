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
	if g.MaxCol() != 7*24-1 {
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
	if g = g.Now(); g.Col != 0 {
		t.Errorf("Now: %d", g.Col)
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
