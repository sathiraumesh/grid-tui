package views

import (
	"strings"
	"testing"
	"time"

	"github.com/charmbracelet/lipgloss"

	"grid-tui/models"
)

// sampleGantt, now 14:30: gros-1 runs job 4521 13:30→16:30, then job 4600
// 18:00→20:00 on gros-1 and gros-2; gros-2 has a besteffort job until 15:00;
// gros-10 is dead.
func sampleGantt() models.Gantt {
	nodes := []models.NodeStatus{
		{Name: "gros-1", Hard: "alive", Reservations: []models.Reservation{
			{JobID: 4521, User: "bob", Queue: "default", State: "Running", Start: at(-1), End: at(2)},
			{JobID: 4600, User: "eve", Queue: "default", State: "Waiting", Start: at(3.5), End: at(5.5)},
		}},
		{Name: "gros-2", Hard: "alive", Reservations: []models.Reservation{
			{JobID: 9, Queue: "besteffort", Start: at(-0.5), End: at(0.5)},
			{JobID: 4600, User: "eve", Queue: "default", State: "Waiting", Start: at(3.5), End: at(5.5)},
		}},
		{Name: "gros-10", Hard: "dead"},
	}
	d := models.NewClusterDetail("nancy", models.Cluster{UID: "gros"}).WithNodes(nodes, now)
	return models.NewGantt(d)
}

// row is the line of node name in the time line, without the name.
func row(t *testing.T, lines []string, name string) string {
	t.Helper()
	for _, l := range lines[ganttHeader:] {
		if f := strings.Fields(l); len(f) > 0 && (f[0] == name || len(f) > 1 && f[1] == name) {
			_, rest, _ := strings.Cut(l, name+" ")
			return strings.TrimLeft(rest, " ")
		}
	}
	t.Fatalf("no row for %s in\n%s", name, strings.Join(lines, "\n"))
	return ""
}

func TestGanttRows(t *testing.T) {
	lines := GanttView{Gantt: sampleGantt()}.LinesFor(40)
	// Cells from 14:00, an hour each: job 4521 14-17 (3 cells: too short
	// for its number), free 17-18, job 4600 18-20, then free.
	if got := row(t, lines, "gros-1"); !strings.HasPrefix(got, "███·██···") {
		t.Errorf("gros-1 = %q", got)
	}
	if got := row(t, lines, "gros-2"); !strings.HasPrefix(got, "░···██···") {
		t.Errorf("gros-2 = %q", got)
	}
	if got := row(t, lines, "gros-10"); strings.Trim(got, "×") != "" {
		t.Errorf("a dead node is × all along: %q", got)
	}
	for i, l := range lines {
		if w := lipgloss.Width(l); w > 40 {
			t.Errorf("line %d is %d wide, more than 40: %q", i, w, l)
		}
	}
}

func TestGanttRowsShowNowAndFree(t *testing.T) {
	g := sampleGantt()
	lines := GanttView{Gantt: g}.LinesFor(40)
	free := lines[6]
	if !strings.HasPrefix(strings.TrimSpace(free), "FREE") {
		t.Fatalf("FREE row = %q", free)
	}
	// 14:00: gros-2 (besteffort only) is free, gros-1 isn't: 1 of 2.
	// 17:00: both free. 18:00: none.
	cells := []rune(strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(free), "FREE")))
	if cells[0] != '▄' || cells[3] != '█' || cells[4] != '·' {
		t.Errorf("FREE cells = %q", string(cells))
	}
}

func TestGanttHeader(t *testing.T) {
	v := GanttView{Gantt: sampleGantt().MoveTime(4)} // 18:00, gros-1: job 4600
	lines := v.LinesFor(100)
	if !strings.Contains(lines[0], "zoom 1h per cell") || !strings.Contains(lines[0], "cursor 18:00") {
		t.Errorf("zoom line = %q", lines[0])
	}
	if want := "gros-1 · #4600 eve · default · Waiting · 18:00→20:00 (2h) · on 2 nodes"; lines[1] != want {
		t.Errorf("selected = %q\nwant       %q", lines[1], want)
	}
	if !strings.Contains(lines[4], "Sun 22") {
		t.Errorf("day row = %q", lines[4])
	}
	if !strings.Contains(lines[5], "18:00") || !strings.Contains(lines[5], "00:00") {
		t.Errorf("hour row = %q", lines[5])
	}
	// The ▲ is under the 5th cell (18:00): after "  ", the names (7) and " ".
	if cursor := []rune(lines[7]); len(cursor) != 2+7+1+4+1 || cursor[len(cursor)-1] != '▲' {
		t.Errorf("cursor row = %q", lines[7])
	}
}

func TestGanttSelectedFreeAndDown(t *testing.T) {
	g := sampleGantt().MoveTime(3) // 17:00
	if got := (GanttView{Gantt: g}).LinesFor(100)[1]; got != "gros-1 · free 16:30→18:00 (1h30m)" {
		t.Errorf("free node = %q", got)
	}
	g = g.Move(2) // gros-10
	if got := (GanttView{Gantt: g}).LinesFor(100)[1]; got != "gros-10 · down (dead)" {
		t.Errorf("down node = %q", got)
	}
}

func TestGanttScrollsToTheCursor(t *testing.T) {
	g := sampleGantt().MoveTime(100)
	lines := GanttView{Gantt: g}.LinesFor(40)
	if !strings.HasSuffix(lines[7], "▲") {
		t.Errorf("the cursor should be at the right edge: %q", lines[7])
	}
	if strings.Contains(row(t, lines, "gros-1"), "#4521") {
		t.Error("scrolled past the first job")
	}
}

func TestGanttZoomLabels(t *testing.T) {
	cases := map[time.Duration]time.Duration{
		15 * time.Minute: 2 * time.Hour,
		time.Hour:        6 * time.Hour,
		4 * time.Hour:    24 * time.Hour,
		12 * time.Hour:   0,
	}
	for cell, want := range cases {
		if got := labelStep(cell); got != want {
			t.Errorf("labelStep(%v) = %v, want %v", cell, got, want)
		}
	}
}

func TestGanttOnScreen(t *testing.T) {
	v := GanttView{Gantt: sampleGantt()}
	s := Render(v, Status{}, 100, 24)
	for _, want := range []string{"cluster: gros", "reservations", "zoom: 1h", "FREE", "gros-1", "#4521", "▲", "[ ] jobs"} {
		if !strings.Contains(s, want) {
			t.Errorf("screen missing %q:\n%s", want, s)
		}
	}
	if lines := strings.Split(s, "\n"); len(lines) != 24 {
		t.Errorf("%d lines, want 24", len(lines))
	}
	if MaxScrollX(v, 100) != 0 {
		t.Error("the time line fits the width: no sideways scrolling")
	}
}

func TestGanttLoading(t *testing.T) {
	g := models.NewGantt(models.NewClusterDetail("nancy", models.Cluster{UID: "gros"}))
	if s := Render(GanttView{Gantt: g}, Status{Loading: true}, 100, 24); !strings.Contains(s, emptyText) || !strings.Contains(s, "loading…") {
		t.Errorf("loading:\n%s", s)
	}
}

func TestJobColorsDifferForJobsNextToEachOther(t *testing.T) {
	c := jobColorsOf(sampleGantt())
	if len(c) != 2 || c[4521] == c[4600] {
		t.Errorf("colors = %v", c)
	}
}

func TestGanttJobNumbersFitWhenZoomedIn(t *testing.T) {
	g := sampleGantt().ZoomBy(-2) // 15 min: job 4521 is 8 cells from 14:30
	if got := row(t, GanttView{Gantt: g}.LinesFor(60), "gros-1"); !strings.HasPrefix(got, "#4521███") {
		t.Errorf("gros-1 at 15 min = %q", got)
	}
	g = sampleGantt().ZoomBy(-1) // 30 min: 4 cells, "4521" without the #
	if got := row(t, GanttView{Gantt: g}.LinesFor(60), "gros-1"); !strings.HasPrefix(got, "4521") {
		t.Errorf("gros-1 at 30 min = %q", got)
	}
}
