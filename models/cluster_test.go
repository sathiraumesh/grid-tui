package models

import (
	"testing"
	"time"
)

var t0 = time.Date(2026, 11, 22, 14, 30, 0, 0, time.Local)

func hours(h float64) time.Time { return t0.Add(time.Duration(h * float64(time.Hour))) }

// sampleNodes: gros-10 is dead; gros-2 runs a job now..+2h; gros-1 has only
// a besteffort job now and a regular one at +3h..+5h.
func sampleNodes() []NodeStatus {
	return []NodeStatus{
		{Name: "gros-10", Hard: "dead"},
		{Name: "gros-2", Hard: "alive", Reservations: []Reservation{
			{JobID: 7, User: "bob", Queue: "default", Start: hours(-1), End: hours(2)},
		}},
		{Name: "gros-1", Hard: "alive", Reservations: []Reservation{
			{JobID: 9, Queue: "default", Start: hours(3), End: hours(5)},
			{JobID: 8, Queue: "besteffort", Start: hours(-2), End: hours(1)},
		}},
	}
}

func TestWithNodesSortsByNumber(t *testing.T) {
	d := NewClusterDetail("nancy", Cluster{UID: "gros"}).WithNodes(sampleNodes(), t0)
	got := []string{d.Nodes[0].Name, d.Nodes[1].Name, d.Nodes[2].Name}
	if got[0] != "gros-1" || got[1] != "gros-2" || got[2] != "gros-10" {
		t.Errorf("order = %v", got)
	}
	if d.At != t0 || d.Len() != 3 {
		t.Errorf("At=%v Len=%d", d.At, d.Len())
	}
}

func TestSlotAt(t *testing.T) {
	d := NewClusterDetail("nancy", Cluster{}).WithNodes(sampleNodes(), t0)
	g1, g2, g10 := d.Nodes[0], d.Nodes[1], d.Nodes[2]
	cases := []struct {
		node     NodeStatus
		from, to float64
		want     Slot
	}{
		{g1, 0, 1, SlotBestEffort},
		{g1, 1, 3, SlotFree}, // ends exactly when the next starts: no overlap
		{g1, 2.5, 3.5, SlotBusy},
		{g2, 0, 1, SlotBusy},
		{g2, 2, 3, SlotFree},
		{g10, 0, 1, SlotDown},
	}
	for _, c := range cases {
		if got := c.node.SlotAt(hours(c.from), hours(c.to)); got != c.want {
			t.Errorf("%s [%v,%v): %v, want %v", c.node.Name, c.from, c.to, got, c.want)
		}
	}
}

func TestCountsNow(t *testing.T) {
	c := NewClusterDetail("nancy", Cluster{}).WithNodes(sampleNodes(), t0).CountsNow()
	if c != (Counts{Alive: 2, Free: 1, Busy: 1, Down: 1}) {
		t.Errorf("counts = %+v", c)
	}
}

func TestUpcoming(t *testing.T) {
	d := NewClusterDetail("nancy", Cluster{}).WithNodes(sampleNodes(), t0)
	up := d.Nodes[0].Upcoming(hours(2)) // the besteffort job ended at +1h
	if len(up) != 1 || up[0].JobID != 9 {
		t.Errorf("upcoming = %+v", up)
	}
}

func TestDetailMoveAndSelected(t *testing.T) {
	d := NewClusterDetail("nancy", Cluster{}).WithNodes(sampleNodes(), t0).Move(5)
	if n, ok := d.Selected(); !ok || n.Name != "gros-10" {
		t.Errorf("selected = %q", n.Name)
	}
	if _, ok := NewClusterDetail("nancy", Cluster{}).Selected(); ok {
		t.Error("no nodes: nothing selected")
	}
}
