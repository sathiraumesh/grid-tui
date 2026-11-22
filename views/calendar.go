package views

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"

	"grid-tui/models"
)

// The week and the month views of a cluster's reservations (GanttView
// draws them when its Mode says so).
//
// Week: a column per day (Monday to Sunday), a row per 2-hour slot. Each
// slot says how many nodes are free all through it, on green (half of
// them or more), amber (fewer) or red (none).
//
//	week of Mon 23 Nov · 2h slots · cursor Mon 23 14:00
//	Mon 23 14:00–16:00 · 37 of 124 nodes free all through · 5 jobs, 2 start
//	…legend…
//
//	        Mon 23     Tue 24     Wed 25     …
//	00:00   124 free   124 free   124 free
//	…
//	14:00   37 free    80 free    124 free
//	14:37 ━━━━━━━━━━━─────────────────────────  ← now: red on today, dim on the others
//	16:00   40 free    124 free   124 free
//	…
//
// Month: a calendar, Monday first. Each day says when it has the fewest
// and the most free nodes, and how many jobs start.
//
//	November 2026 · cursor Mon 23 Nov
//	Mon 23 Nov · 12–40 of 124 nodes free · 7 jobs start
//	…legend…
//
//	Mon          Tue          Wed          …
//	23  7 jobs   24  2 jobs   25
//	12–40 free   80–124 free  124 free
//	…

// The calendar's colours: how many nodes are free.
var (
	manyFree = lipgloss.NewStyle().Background(lipgloss.Color("#1F6F3F")).Foreground(lipgloss.Color("#FFFFFF"))
	someFree = lipgloss.NewStyle().Background(lipgloss.Color("#8A6200")).Foreground(lipgloss.Color("#FFFFFF"))
	noFree   = lipgloss.NewStyle().Background(lipgloss.Color("#8B1E1E")).Foreground(lipgloss.Color("#FFFFFF"))
	pastCell = lipgloss.NewStyle().Foreground(lipgloss.Color("#5A5A5A"))
	today    = lipgloss.NewStyle().Bold(true).Underline(true)
)

// calendar header lines: the info (3) and an empty line, then the days.
const (
	weekHeader  = 5 // + the day names
	monthHeader = 5 // + the weekday names
)

// freeStyle colours a count of free nodes out of usable.
func freeStyle(free, usable int) lipgloss.Style {
	switch {
	case free == 0:
		return noFree
	case free*2 >= usable:
		return manyFree
	}
	return someFree
}

func calendarLegend() string {
	return manyFree.Render(" half or more free ") + " " + someFree.Render(" fewer ") + " " +
		noFree.Render(" none ") + "  " + selJob.Render(" cursor ") + "  " + pastCell.Render("· past or not shown")
}

// monday is the start of t's week.
func monday(t time.Time) time.Time {
	d := time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, t.Location())
	return d.AddDate(0, 0, -((int(d.Weekday()) + 6) % 7))
}

// cellText is text cut or padded to w columns, then a space.
func cellText(text string, w int) string {
	return pad(ansi.Truncate(text, w, ""), w) + " "
}

// weekLines draws the week of the cursor to fill width columns.
func (v GanttView) weekLines(width int) []string {
	g := v.Gantt
	now, cur := g.Now(), g.Day
	start := monday(cur)
	colW := max((width-6)/7-1, 4) // the time column is "00:00 "

	from, to := cur, cur.Add(models.WeekSlot)
	free, usable := g.FreeBetween(from, to)
	detail := fmt.Sprintf("%s %s–%s · %d of %d nodes free all through · %s, %d start",
		cur.Format("Mon 02"), cur.Format("15:04"), to.Format("15:04"), free, usable,
		jobs(g.JobsDuring(from, to)), g.JobsStarting(from, to))

	lines := []string{
		Help.Render(fmt.Sprintf("week of %s · %s slots · cursor %s", start.Format("Mon 02 Jan"), duration(models.WeekSlot), clock(cur, now))),
		freeStyle(free, usable).Render(detail),
		calendarLegend(),
		"",
	}
	head := "      "
	for d := range 7 {
		day := start.AddDate(0, 0, d)
		name := cellText(day.Format("Mon 02"), colW)
		if day.Equal(monday(now).AddDate(0, 0, (int(now.Weekday())+6)%7)) {
			name = today.Render(strings.TrimRight(name, " ")) + " "
		}
		head += name
	}
	lines = append(lines, head)

	nowSlot, nowDay := v.nowInWeek(start)
	for i, slot := 0, time.Duration(0); slot < 24*time.Hour; i, slot = i+1, slot+models.WeekSlot {
		row := start.Add(slot).Format("15:04") + " "
		for d := range 7 {
			from := start.AddDate(0, 0, d).Add(slot)
			to := from.Add(models.WeekSlot)
			row += v.slotCell(from, to, colW)
		}
		lines = append(lines, row)
		if i == nowSlot {
			lines = append(lines, nowLine(now, nowDay, colW))
		}
	}
	return lines
}

// nowInWeek is the slot (row) and the day (column) holding now in the
// week starting at start, or -1, -1 if now isn't in it.
func (v GanttView) nowInWeek(start time.Time) (slot, day int) {
	now := v.Gantt.Now()
	if now.Before(start) || !now.Before(start.AddDate(0, 0, 7)) {
		return -1, -1
	}
	return int(now.Sub(midnight(now)) / models.WeekSlot), int(midnight(now).Sub(start).Hours()+0.5) / 24
}

// nowLine is the line across the week at the current time: its clock in
// the time column, then bright red on today's column and dim on the others.
func nowLine(now time.Time, day, colW int) string {
	line := nowStyle.Bold(true).Render(now.Format("15:04")) + " "
	for d := range 7 {
		cell := strings.Repeat("─", colW) + " "
		if d == day {
			line += nowStyle.Bold(true).Render(strings.Repeat("━", colW+1))
			continue
		}
		line += pastCell.Render(cell)
	}
	return line
}

// slotCell is one slot of the week: its free nodes in its colour, dim if
// it is over (or past the shown time), in the cursor's colour if it is
// the cursor's.
func (v GanttView) slotCell(from, to time.Time, w int) string {
	g := v.Gantt
	if !to.After(g.Now()) || !from.Before(g.End()) {
		return pastCell.Render(cellText("·", w))
	}
	free, usable := g.FreeBetween(from, to)
	text := fmt.Sprintf("%d free", free)
	if w < len(text) {
		text = fmt.Sprint(free)
	}
	st := freeStyle(free, usable)
	if from.Equal(g.Day) {
		st = selJob
	}
	return st.Render(pad(ansi.Truncate(text, w, ""), w)) + " "
}

// weekFocus is the line of the cursor's slot, the now line counted.
func (v GanttView) weekFocus() int {
	d := v.Gantt.Day
	slot := int(d.Sub(midnight(d)) / models.WeekSlot)
	if nowSlot, _ := v.nowInWeek(monday(d)); nowSlot >= 0 && slot > nowSlot {
		slot++ // the now line is above it
	}
	return weekHeader + slot
}

// monthLines draws the month of the cursor to fill width columns.
func (v GanttView) monthLines(width int) []string {
	g := v.Gantt
	now, cur := g.Now(), g.Day
	first := time.Date(cur.Year(), cur.Month(), 1, 0, 0, 0, 0, cur.Location())
	colW := max(width/7-1, 6)

	least, most, usable := g.DayFree(cur)
	detail := fmt.Sprintf("%s · %s of %d nodes free · %s start",
		cur.Format("Mon 02 Jan"), span(least, most), usable, jobs(g.JobsStarting(cur, cur.AddDate(0, 0, 1))))
	if cur.Before(midnight(now)) || !cur.Before(g.End()) {
		detail = cur.Format("Mon 02 Jan") + " · not shown: only now to " + g.End().Format("Mon 02 Jan") + " is known"
	}

	lines := []string{
		Help.Render(fmt.Sprintf("%s · cursor %s", first.Format("January 2006"), cur.Format("Mon 02 Jan"))),
		freeStyle(least, max(usable, 1)).Render(detail),
		calendarLegend(),
		"",
	}
	head := ""
	for _, name := range []string{"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"} {
		head += cellText(name, colW)
	}
	lines = append(lines, Header.Render(head))

	for week := monday(first); week.Month() == first.Month() || week.Before(first); week = week.AddDate(0, 0, 7) {
		top, bottom := "", ""
		for d := range 7 {
			day := week.AddDate(0, 0, d)
			t, b := v.dayCell(day, first.Month(), colW)
			top, bottom = top+t, bottom+b
		}
		lines = append(lines, top, bottom)
	}
	return lines
}

// dayCell is one day of the month, on two lines: its number and how many
// jobs start, then its free nodes, in its colour.
func (v GanttView) dayCell(day time.Time, month time.Month, w int) (string, string) {
	g := v.Gantt
	now := g.Now()
	num := fmt.Sprintf("%2d", day.Day())
	if day.Month() != month {
		return pastCell.Render(cellText(num, w)), cellText("", w)
	}
	if day.Before(midnight(now)) || !day.Before(g.End()) {
		return pastCell.Render(cellText(num, w)), pastCell.Render(cellText("·", w))
	}
	least, most, usable := g.DayFree(day)
	top := num
	if n := g.JobsStarting(day, day.AddDate(0, 0, 1)); n > 0 {
		top += "  " + jobs(n)
	}
	st := freeStyle(least, usable)
	if day.Equal(g.Day) {
		st = selJob
	}
	topText := cellText(top, w)
	if day.Equal(midnight(now)) {
		topText = today.Render(strings.TrimRight(topText, " ")) + strings.Repeat(" ", w+1-lipgloss.Width(strings.TrimRight(topText, " ")))
	}
	return topText, st.Render(pad(ansi.Truncate(span(least, most)+" free", w, ""), w)) + " "
}

// monthFocus is the line of the cursor's day (its free nodes).
func (v GanttView) monthFocus() int {
	d := v.Gantt.Day
	first := time.Date(d.Year(), d.Month(), 1, 0, 0, 0, 0, d.Location())
	week := int(monday(d).Sub(monday(first)).Hours()/24) / 7
	return monthHeader + 2*week + 1
}

// jobs is "1 job" or "3 jobs".
func jobs(n int) string {
	if n == 1 {
		return "1 job"
	}
	return fmt.Sprintf("%d jobs", n)
}

// span is "12–40", or "40" when both are the same.
func span(least, most int) string {
	if least == most {
		return fmt.Sprint(least)
	}
	return fmt.Sprintf("%d–%d", least, most)
}

// midnight is the start of t's day.
func midnight(t time.Time) time.Time {
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, t.Location())
}
