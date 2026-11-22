package views

import (
	"strings"
	"testing"
	"time"

	"github.com/charmbracelet/lipgloss"

	"grid-tui/models"
)

// now (14:30) is a Sunday; the week of it starts Mon 16 Nov.

func TestWeekView(t *testing.T) {
	g := sampleGantt().WithMode(models.ModeWeek) // cursor: Sun 22 14:00
	v := GanttView{Gantt: g}
	lines := v.LinesFor(100)
	if !strings.HasPrefix(lines[0], "week of Mon 16 Nov") {
		t.Errorf("title = %q", lines[0])
	}
	if want := "Sun 22 14:00–16:00 · 1 of 2 nodes free all through · 1 job, 0 start"; lines[1] != want {
		t.Errorf("detail = %q\nwant     %q", lines[1], want)
	}
	if !strings.Contains(lines[weekHeader-1], "Mon 16") || !strings.Contains(lines[weekHeader-1], "Sun 22") {
		t.Errorf("day names = %q", lines[weekHeader-1])
	}
	// Rows 00:00 … 14:00, then the now line, then 16:00 …
	nowRow := weekHeader + 1 + 14/2
	if !strings.HasPrefix(lines[nowRow], "14:30 ") || !strings.Contains(lines[nowRow], "━") {
		t.Errorf("now line = %q", lines[nowRow])
	}
	if !strings.HasPrefix(lines[nowRow-1], "14:00") || !strings.HasPrefix(lines[nowRow+1], "16:00") {
		t.Errorf("the now line is between 14:00 and 16:00: %q / %q", lines[nowRow-1], lines[nowRow+1])
	}
	if v.Focus() != nowRow-1 {
		t.Errorf("focus = %d, want the 14:00 row %d", v.Focus(), nowRow-1)
	}
	if v2 := (GanttView{Gantt: g.MoveDay(0, 1)}); v2.Focus() != nowRow+1 {
		t.Errorf("below the now line, focus counts it: %d", v2.Focus())
	}
	// Sunday's 14:00 slot (the cursor) has 1 free; Monday the 16th is past.
	if row := lines[nowRow-1]; !strings.Contains(row, "1 free") || !strings.Contains(row, "·") {
		t.Errorf("14:00 row = %q", row)
	}
	for i, l := range lines {
		if lipgloss.Width(l) > 100 {
			t.Errorf("line %d is wider than 100: %q", i, l)
		}
	}
}

func TestWeekNowLineMovesWithTheClock(t *testing.T) {
	g := sampleGantt().WithClock(now.Add(3 * time.Hour)).WithMode(models.ModeWeek) // 17:30
	lines := GanttView{Gantt: g}.LinesFor(100)
	nowRow := weekHeader + 1 + 16/2
	if !strings.HasPrefix(lines[nowRow], "17:30 ") {
		t.Errorf("the now line moved to 17:30, under 16:00: %q", lines[nowRow])
	}
	// Next week has no now line.
	next := GanttView{Gantt: g.MoveDay(7, 0)}.LinesFor(100)
	for _, l := range next {
		if strings.Contains(l, "━") {
			t.Errorf("no now line on another week: %q", l)
		}
	}
}

func TestMonthView(t *testing.T) {
	g := sampleGantt().WithMode(models.ModeMonth) // Sun 22 Nov
	v := GanttView{Gantt: g}
	lines := v.LinesFor(100)
	if !strings.HasPrefix(lines[0], "November 2026") {
		t.Errorf("title = %q", lines[0])
	}
	if want := "Sun 22 Nov · 0–2 of 2 nodes free · 2 jobs start"; lines[1] != want {
		t.Errorf("detail = %q\nwant     %q", lines[1], want)
	}
	if !strings.HasPrefix(lines[monthHeader-1], "Mon") || !strings.Contains(lines[monthHeader-1], "Sun") {
		t.Errorf("weekdays = %q", lines[monthHeader-1])
	}
	// November 2026 starts on a Sunday: 6 weeks, from Mon 26 Oct.
	if weeks := (len(lines) - monthHeader) / 2; weeks != 6 {
		t.Errorf("%d weeks, want 6", weeks)
	}
	// Sun 22 is in the 4th week; the cursor's line is its free nodes.
	if focus := v.Focus(); focus != monthHeader+2*3+1 || !strings.Contains(lines[focus], "0–2 free") {
		t.Errorf("focus %d: %q", focus, lines[v.Focus()])
	}
	if !strings.Contains(lines[monthHeader+2*3], "22  2 jobs") {
		t.Errorf("Sun 22's number line = %q", lines[monthHeader+2*3])
	}
	if next := (GanttView{Gantt: g.MoveDay(1, 0)}).LinesFor(100)[1]; !strings.HasPrefix(next, "Mon 23 Nov · 2 of 2") {
		t.Errorf("Mon 23 = %q", next)
	}
}
