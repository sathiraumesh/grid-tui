package views

import (
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"

	"grid-tui/models"
	"grid-tui/styles"
)

// GanttView draws a cluster's reservations on a time line, a row per node
// and a column per period ("cell"), from now on. Every job has its own
// colour and its number written in it where it fits; the job under the
// time cursor is highlighted on every node it holds. A FREE row on top
// shows how many nodes are free in each cell.
//
//	zoom 1h per cell · Sun 22 14:00 → Sun 29 14:00 · cursor Sun 22 18:00
//	gros-2 · #4600 eve · default · Waiting · 18:00→20:00 (2h) · on 2 nodes
//	██ job (a colour each)  ░ besteffort  · free  │ now  × down  ▲ cursor
//
//	           Sun 22                    Mon 23
//	           18:00       00:00       06:00
//	  FREE     ▄▄▄▁▁▄██████████████
//	               ▲
//	  gros-1   #4521█··#4600█···············
//	▸ gros-2   ░·····#4600█·················
//	  gros-3   ××××××××××××××××××××××××
type GanttView struct {
	Gantt models.Gantt
}

var (
	_ Fitted  = GanttView{} // fills the panel's width with time
	_ Focused = GanttView{} // keeps the selected node on screen, colours kept
	_ Pinned  = GanttView{} // the info and the time axis stay on screen
)

// The time line's colours. Jobs take turns through jobColors in the order
// they start, so jobs next to each other get different colours; each state
// has its own: free green, besteffort grey, down and now red, the
// selected job yellow.
var (
	jobColors = []lipgloss.Color{
		"#2563EB", "#EA580C", "#16A34A", "#9333EA", "#DC2626", "#0891B2", "#CA8A04", "#DB2777",
		"#4F46E5", "#65A30D", "#0D9488", "#C026D3", "#B45309", "#0284C7", "#BE123C", "#7C3AED",
	}
	selJob   = lipgloss.NewStyle().Background(lipgloss.Color("#FDE047")).Foreground(lipgloss.Color("#000000")).Bold(true)
	dimStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#3F7D4E")) // a free cell: dim green
	beStyle  = lipgloss.NewStyle().Foreground(styles.Muted)
	nowStyle = lipgloss.NewStyle().Foreground(styles.StatusBad)
	downCell = lipgloss.NewStyle().Foreground(styles.StatusBad)
	freeBar  = lipgloss.NewStyle().Foreground(styles.StatusOK)
	noneFree = lipgloss.NewStyle().Foreground(styles.StatusBad)
)

// ganttHeader is how many lines come before the nodes: the info (3), an
// empty line, the days, the hours, the FREE row and the cursor row.
const ganttHeader = 8

func (v GanttView) Labels() []string {
	d := v.Gantt.Detail
	return []string{"site: " + d.Site, "cluster: " + d.Cluster.UID, "reservations", "zoom: " + duration(v.Gantt.Cell())}
}

func (v GanttView) Command() string {
	d := v.Gantt.Detail
	return "curl https://api.grid5000.fr/stable/sites/" + d.Site + "/clusters/" + d.Cluster.UID + "/status"
}

func (v GanttView) Help() string {
	return "↑↓ nodes • ←→ time (H L a day) • [ ] jobs • + - zoom • n now • esc detail • r reload • q quit"
}

// Lines is the time line for a 100 columns wide panel.
func (v GanttView) Lines() []string { return v.LinesFor(100) }

// Pinned keeps the info and the time axis on screen.
func (v GanttView) Pinned() int { return ganttHeader }

// Focus is the selected node's row.
func (v GanttView) Focus() int {
	if v.Gantt.Len() == 0 {
		return -1
	}
	return ganttHeader + v.Gantt.Detail.Cursor
}

// LinesFor draws the time line to fill width columns.
func (v GanttView) LinesFor(width int) []string {
	g := v.Gantt
	if g.Detail.At.IsZero() {
		return nil // still loading: the panel says there is nothing yet
	}
	nameW := lipgloss.Width("FREE")
	for _, n := range g.Detail.Nodes {
		nameW = max(nameW, lipgloss.Width(n.Name))
	}
	left := 2 + nameW + 1 // "▸ " + name + " "
	cols := max(width-left, 1)

	// The cells on screen, scrolled to keep the time cursor in sight.
	first := 0
	if g.Col >= cols {
		first = g.Col - cols + 1
	}
	end := min(first+cols, g.MaxCol()+1)

	fit := func(s string) string { return ansi.Truncate(s, width, "…") } // no sideways scrolling
	lines := []string{
		fit(Help.Render(v.zoomLine())),
		fit(v.selectedLine()),
		fit(legend()),
		"",
		strings.Repeat(" ", left) + v.dayRow(first, end),
		strings.Repeat(" ", left) + v.hourRow(first, end),
		"  " + pad("FREE", nameW) + " " + v.freeRow(first, end),
		strings.Repeat(" ", left+g.Col-first) + "▲",
	}
	if g.Len() == 0 {
		return append(lines, Help.Render("no nodes"))
	}
	_, sel, hasSel := g.Selected()
	colors := jobColorsOf(g)
	for i, n := range g.Detail.Nodes {
		mark, name := "  ", pad(n.Name, nameW)
		if i == g.Detail.Cursor {
			mark, name = "▸ ", Selected.Render(name)
		}
		selID := int64(-1)
		if hasSel {
			selID = sel.JobID
		}
		lines = append(lines, mark+name+" "+v.nodeRow(n, first, end, selID, i == g.Detail.Cursor, colors))
	}
	return lines
}

// zoomLine is e.g. "zoom 1h per cell · Sun 22 14:00 → Sun 29 14:00 · cursor 18:00".
func (v GanttView) zoomLine() string {
	g := v.Gantt
	now := g.Detail.At
	last := g.CellStart(g.MaxCol() + 1)
	return fmt.Sprintf("zoom %s per cell · %s → %s · cursor %s",
		duration(g.Cell()), clock(g.Origin(), now.Add(-48*time.Hour)), clock(last, now), clock(g.CursorTime(), now))
}

// selectedLine describes the selected node at the time cursor: its job,
// or how long it is free.
func (v GanttView) selectedLine() string {
	g := v.Gantt
	now := g.Detail.At
	n, r, has := g.Selected()
	switch {
	case g.Len() == 0:
		return ""
	case !n.Usable():
		return n.Name + " · down (" + n.Hard + ")"
	case has:
		text := fmt.Sprintf("%s · #%d %s · %s · %s · %s→%s (%s) · on %d nodes",
			n.Name, r.JobID, orDash(r.User), orDash(r.Queue), orDash(r.State),
			clock(r.Start, now), clock(r.End, now), duration(r.End.Sub(r.Start)), g.JobNodes(r.JobID))
		return selJob.Render(text)
	}
	from, to := g.FreeSpan(n)
	if to.IsZero() {
		return freeBar.Render(fmt.Sprintf("%s · free from %s, no job after", n.Name, clock(from, now)))
	}
	return freeBar.Render(fmt.Sprintf("%s · free %s→%s (%s)", n.Name, clock(from, now), clock(to, now), duration(to.Sub(from))))
}

func legend() string {
	swatch := func(c lipgloss.Color) string { return lipgloss.NewStyle().Background(c).Render(" ") }
	return swatch(jobColors[0]) + swatch(jobColors[1]) + swatch(jobColors[2]) + " jobs (a colour each)  " +
		selJob.Render(" ") + " selected job  " + beStyle.Render("░") + " besteffort  " +
		dimStyle.Render("·") + " free  " + nowStyle.Render("│") + " now  " + downCell.Render("×") + " down  ▲ cursor"
}

// dayRow writes the day ("Mon 23") where each day starts.
func (v GanttView) dayRow(first, end int) string {
	row := []rune(strings.Repeat(" ", end-first))
	free := 0 // first column a label may start at
	for col := first; col < end; col++ {
		t := v.Gantt.CellStart(col)
		if col != first && v.Gantt.CellStart(col-1).Day() == t.Day() {
			continue
		}
		free = place(row, col-first, free, t.Format("Mon 02"))
	}
	return string(row)
}

// hourRow writes the time ("18:00") every few cells, on round times.
func (v GanttView) hourRow(first, end int) string {
	row := []rune(strings.Repeat(" ", end-first))
	step := labelStep(v.Gantt.Cell())
	if step == 0 {
		return string(row)
	}
	free := 0
	for col := first; col < end; col++ {
		t := v.Gantt.CellStart(col)
		midnight := time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, t.Location())
		if t.Sub(midnight)%step == 0 {
			free = place(row, col-first, free, t.Format("15:04"))
		}
	}
	return string(row)
}

// labelStep is how often to write a time: the shortest round period at
// least 6 cells long ("18:00" and a space), or 0 if none (days only).
func labelStep(cell time.Duration) time.Duration {
	for _, s := range []time.Duration{15 * time.Minute, 30 * time.Minute, time.Hour, 2 * time.Hour,
		3 * time.Hour, 6 * time.Hour, 12 * time.Hour, 24 * time.Hour} {
		if s >= cell && s/cell >= 6 {
			return s
		}
	}
	return 0
}

// place writes label into row at i if it fits after free; it returns the
// next free column.
func place(row []rune, i, free int, label string) int {
	l := []rune(label)
	if i < free || i+len(l) > len(row) {
		return free
	}
	copy(row[i:], l)
	return i + len(l) + 1
}

// freeRow is a bar per cell, as high as the share of nodes free: ▁ to █,
// or a red · when none is.
func (v GanttView) freeRow(first, end int) string {
	const bars = "▁▂▃▄▅▆▇█"
	var r runs
	for col := first; col < end; col++ {
		free, usable := v.Gantt.FreeIn(col)
		switch {
		case usable == 0:
			r.add(" ", "", lipgloss.NewStyle())
		case free == 0:
			r.add("·", "none", noneFree)
		default:
			level := (free*len([]rune(bars)) - 1) / usable // 1 free of many: ▁; all: █
			r.add(string([]rune(bars)[level]), "free", freeBar)
		}
	}
	return r.String()
}

// nodeRow draws one node's cells: its jobs in their colours with their
// numbers, besteffort ░, free ·, now │, down ×. The cell under the cursor
// of the selected node is reversed.
func (v GanttView) nodeRow(n models.NodeStatus, first, end int, selID int64, selected bool, colors map[int64]lipgloss.Color) string {
	g := v.Gantt
	type cell struct {
		ch    string
		key   string
		style lipgloss.Style
	}
	cells := make([]cell, 0, end-first)
	ids := make([]int64, 0, end-first) // the job in each cell, -1 if none
	for col := first; col < end; col++ {
		c, id := cell{ch: "·", key: "free", style: dimStyle}, int64(-1)
		switch r, has := g.JobIn(n, col); {
		case !n.Usable():
			c = cell{"×", "down", downCell}
		case has && !r.BestEffort():
			// A solid block in the job's colour; its number goes in later
			// where it fits.
			id = r.JobID
			fg := colors[r.JobID]
			if r.JobID == selID {
				fg = selJob.GetBackground().(lipgloss.Color)
			}
			c = cell{"█", "job" + strconv.FormatInt(r.JobID, 10), lipgloss.NewStyle().Foreground(fg)}
		case has:
			c = cell{"░", "be", beStyle}
		case col == 0:
			c = cell{"│", "now", nowStyle} // the cell holding now
		}
		if selected && col == g.Col {
			c.style, c.key = c.style.Reverse(true), c.key+"cur"
		}
		cells = append(cells, c)
		ids = append(ids, id)
	}

	// Write each job's number at the start of its run of cells, where it
	// fits: "#4521", or "4521" if the run is one cell shorter. The number
	// is drawn on the job's colour.
	for i := 0; i < len(ids); {
		j := i
		for j < len(ids) && ids[j] == ids[i] {
			j++
		}
		if ids[i] >= 0 {
			num := strconv.FormatInt(ids[i], 10)
			label := []rune("#" + num)
			if len(label) > j-i {
				label = []rune(num)
			}
			if len(label) <= j-i {
				bg := colors[ids[i]]
				text := lipgloss.NewStyle().Background(bg).Foreground(lipgloss.Color("#FFFFFF")).Bold(true)
				if ids[i] == selID {
					text = selJob
				}
				for k, ch := range label {
					c := &cells[i+k]
					c.ch, c.key = string(ch), c.key+"label"
					cur := c.style.GetReverse()
					c.style = text.Reverse(cur)
				}
			}
		}
		i = j
	}

	var r runs
	for _, c := range cells {
		r.add(c.ch, c.key, c.style)
	}
	return r.String()
}

// jobColorsOf gives every regular job a colour, taking turns through
// jobColors in the order the jobs start: two jobs next to each other in
// time (or on nodes next to each other) don't share one.
func jobColorsOf(g models.Gantt) map[int64]lipgloss.Color {
	type job struct {
		id    int64
		start time.Time
	}
	var jobs []job
	seen := map[int64]bool{}
	for _, n := range g.Detail.Nodes {
		for _, r := range n.Reservations {
			if !r.BestEffort() && !seen[r.JobID] {
				seen[r.JobID] = true
				jobs = append(jobs, job{r.JobID, r.Start})
			}
		}
	}
	sort.Slice(jobs, func(i, j int) bool {
		if !jobs[i].start.Equal(jobs[j].start) {
			return jobs[i].start.Before(jobs[j].start)
		}
		return jobs[i].id < jobs[j].id
	})
	colors := make(map[int64]lipgloss.Color, len(jobs))
	for i, j := range jobs {
		colors[j.id] = jobColors[i%len(jobColors)]
	}
	return colors
}

// runs gathers cells of the same style, to draw each run with one Render.
type runs struct {
	b      strings.Builder
	text   strings.Builder
	key    string
	style  lipgloss.Style
	active bool
}

func (r *runs) add(ch, key string, style lipgloss.Style) {
	if r.active && key != r.key {
		r.flush()
	}
	if !r.active {
		r.key, r.style, r.active = key, style, true
	}
	r.text.WriteString(ch)
}

func (r *runs) flush() {
	r.b.WriteString(r.style.Render(r.text.String()))
	r.text.Reset()
	r.active = false
}

func (r *runs) String() string {
	if r.active {
		r.flush()
	}
	return r.b.String()
}

// pad is s followed by spaces up to w columns.
func pad(s string, w int) string {
	return s + strings.Repeat(" ", max(w-lipgloss.Width(s), 0))
}
