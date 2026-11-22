package controllers

import (
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// A cluster's reservations on a time line. It opens from a cluster's
// detail (enter) or straight from the clusters (g), and esc goes back to
// where it was opened from. Its data is the detail's (loadDetail): opened
// from the clusters, it loads first; r loads it again.
//
// Three views: t the time line, w a week, m a month (v: the next one).
//
// Keys on the time line:
//
//	↑↓          nodes
//	←→ (h l)    the time cursor, a cell at a time; H L a day
//	[ ]         the previous / next job of the node
//	+ -         zoom in (shorter cells) / out
//
// On the week: ←→ days, ↑↓ 2-hour slots, [ ] weeks. On the month: ←→
// days, ↑↓ weeks, [ ] months. enter on either opens the time line there.
// n goes back to now, in every view.
//
// While it is open a clock ticks (clockEvery): the now marks move with the
// time, with no call to the API. Each opening starts a new clock (gen),
// and ticks of an older one, or after leaving, stop there.

// clockEvery is how often the time now is updated on the reservations.
var clockEvery = 30 * time.Second

// clockMsg is a tick of the clock started as generation gen.
type clockMsg struct {
	at  time.Time
	gen int
}

// tick waits clockEvery, then sends a tick of generation gen.
func tick(gen int) tea.Cmd {
	return tea.Tick(clockEvery, func(t time.Time) tea.Msg { return clockMsg{at: t, gen: gen} })
}

// startClock starts a new clock for the reservations just opened.
func (c Controller) startClock() (Controller, tea.Cmd) {
	c.clockGen++
	return c, tick(c.clockGen)
}

// onClock moves the now marks and waits for the next tick, while the
// reservations are on screen and this is their clock.
func (c Controller) onClock(msg clockMsg) (Controller, tea.Cmd) {
	g, onGantt := c.model.(models.Gantt)
	if !onGantt || msg.gen != c.clockGen {
		return c, nil // left, or an older clock: it stops here
	}
	c.model = g.WithClock(msg.at)
	return c, tick(c.clockGen)
}

// openGantt shows the reservations of the cluster on screen (a detail with
// its nodes loaded) or of the selected one in the clusters list.
func (c Controller) openGantt() (tea.Model, tea.Cmd) {
	switch m := c.model.(type) {
	case models.ClusterDetail:
		if m.Len() == 0 {
			return c, nil // nothing to draw yet
		}
		c.ganttFrom = m
		c.model = models.NewGantt(m).WithClock(time.Now())
		return c.startClock()
	case models.Clusters:
		if c.client == nil || c.loading {
			return c, nil
		}
		cl, ok := m.Selected()
		if !ok {
			return c, nil
		}
		c.returnTo = c.clusters // the detail behind it, if esc'd to, goes back here too
		c.ganttFrom = c.clusters
		c.model = models.NewGantt(models.NewClusterDetail(m.Site, cl))
		c.loading, c.err, c.scrollX = true, nil, 0
		c, clock := c.startClock()
		return c, tea.Batch(loadDetail(c.client, m.Site, cl.UID), clock)
	}
	return c, nil
}

// onGanttKey is what keys do on the time line.
func (c Controller) onGanttKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	g := c.model.(models.Gantt)
	switch msg.String() {
	case keyQuit, keyCtrlC:
		return c, tea.Quit
	case keyBack, keyBackAlt:
		return c.backFromGantt(g), nil
	case keyReload:
		return c.reload()
	case "t":
		g = g.WithMode(models.ModeTimeline)
	case "w":
		g = g.WithMode(models.ModeWeek)
	case "m":
		g = g.WithMode(models.ModeMonth)
	case "v":
		g = g.WithMode((g.Mode + 1) % 3)
	case "n":
		g = g.ToNow()
	default:
		switch g.Mode {
		case models.ModeWeek:
			g = weekKey(g, msg.String())
		case models.ModeMonth:
			g = monthKey(g, msg.String())
		default:
			g = timelineKey(g, msg.String())
		}
	}
	c.model = g
	return c, nil
}

// weekKey is what a key does on the week.
func weekKey(g models.Gantt, key string) models.Gantt {
	switch key {
	case keyLeft, keyLeftAlt:
		return g.MoveDay(-1, 0)
	case keyRight, keyRightAlt:
		return g.MoveDay(1, 0)
	case keyUp, keyUpAlt:
		return g.MoveDay(0, -1)
	case keyDown, keyDownAlt:
		return g.MoveDay(0, 1)
	case "[":
		return g.MoveDay(-7, 0)
	case "]":
		return g.MoveDay(7, 0)
	case keyOpen:
		return g.ZoomTo(1).WithMode(models.ModeTimeline) // 30 min cells: a slot is 4
	}
	return g
}

// monthKey is what a key does on the month.
func monthKey(g models.Gantt, key string) models.Gantt {
	switch key {
	case keyLeft, keyLeftAlt:
		return g.MoveDay(-1, 0)
	case keyRight, keyRightAlt:
		return g.MoveDay(1, 0)
	case keyUp, keyUpAlt:
		return g.MoveDay(-7, 0)
	case keyDown, keyDownAlt:
		return g.MoveDay(7, 0)
	case "[":
		return g.MoveDay(-30, 0)
	case "]":
		return g.MoveDay(30, 0)
	case keyOpen:
		return g.ZoomTo(2).WithMode(models.ModeTimeline) // 1 h cells: the day fills the screen
	}
	return g
}

// timelineKey is what a key does on the time line.
func timelineKey(g models.Gantt, key string) models.Gantt {
	day := int(24 * 60 / g.Cell().Minutes())
	switch key {
	case keyUp, keyUpAlt:
		g = g.Move(-1)
	case keyDown, keyDownAlt:
		g = g.Move(1)
	case keyLeft, keyLeftAlt:
		g = g.MoveTime(-1)
	case keyRight, keyRightAlt:
		g = g.MoveTime(1)
	case "H", "shift+left":
		g = g.MoveTime(-day)
	case "L", "shift+right":
		g = g.MoveTime(day)
	case "[":
		g = g.JumpJob(-1)
	case "]":
		g = g.JumpJob(1)
	case "+", "=":
		g = g.ZoomBy(-1)
	case "-", "_":
		g = g.ZoomBy(1)
	}
	return g
}

// backFromGantt goes back to where the time line was opened from: the
// detail (with the node selected there kept) or the clusters.
func (c Controller) backFromGantt(g models.Gantt) Controller {
	switch from := c.ganttFrom.(type) {
	case models.ClusterDetail:
		d := g.Detail
		if d.At.IsZero() { // never loaded here: the detail as it was
			d = from
		}
		c.model = d
	default:
		c.model = c.clusters
	}
	c.loading, c.err, c.scrollX = false, nil, 0
	return c
}
