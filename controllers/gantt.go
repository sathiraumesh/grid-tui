package controllers

import (
	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// A cluster's reservations on a time line. It opens from a cluster's
// detail (enter) or straight from the clusters (g), and esc goes back to
// where it was opened from. Its data is the detail's (loadDetail): opened
// from the clusters, it loads first; r loads it again.
//
// Keys on the time line:
//
//	↑↓          nodes
//	←→ (h l)    the time cursor, a cell at a time; H L a day
//	[ ]         the previous / next job of the node
//	+ -         zoom in (shorter cells) / out
//	n           back to now

// openGantt shows the reservations of the cluster on screen (a detail with
// its nodes loaded) or of the selected one in the clusters list.
func (c Controller) openGantt() (tea.Model, tea.Cmd) {
	switch m := c.model.(type) {
	case models.ClusterDetail:
		if m.Len() == 0 {
			return c, nil // nothing to draw yet
		}
		c.ganttFrom = m
		c.model = models.NewGantt(m)
		return c, nil
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
		return c, loadDetail(c.client, m.Site, cl.UID)
	}
	return c, nil
}

// onGanttKey is what keys do on the time line.
func (c Controller) onGanttKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	g := c.model.(models.Gantt)
	day := int(24 * 60 / g.Cell().Minutes())
	switch msg.String() {
	case keyQuit, keyCtrlC:
		return c, tea.Quit
	case keyBack, keyBackAlt:
		return c.backFromGantt(g), nil
	case keyReload:
		return c.reload()
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
	case "n":
		g = g.Now()
	default:
		return c, nil
	}
	c.model = g
	return c, nil
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
