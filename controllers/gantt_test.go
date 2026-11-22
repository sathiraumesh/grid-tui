package controllers

import (
	"strings"
	"testing"
	"time"

	"grid-tui/models"
)

// onDetail is a controller showing gros' detail, its nodes loaded.
func onDetail(t *testing.T) Controller {
	t.Helper()
	c, _ := press(t, onClusters(t), "down") // gros
	c, cmd := press(t, c, "enter")
	return run(t, c, cmd)
}

func TestEnterOnTheDetailOpensTheReservations(t *testing.T) {
	c, _ := press(t, onDetail(t), "down") // gros-2
	c, cmd := press(t, c, "enter")
	g, ok := c.Model().(models.Gantt)
	if !ok || cmd != nil {
		t.Fatalf("enter should open the time line with what is loaded: %T", c.Model())
	}
	if n, _, _ := g.Selected(); n.Name != "gros-2" {
		t.Errorf("the node selected on the detail stays selected: %q", n.Name)
	}
	if v := c.View(); !strings.Contains(v, "reservations") || !strings.Contains(v, "FREE") {
		t.Errorf("view:\n%s", v)
	}
	c, _ = press(t, c, "esc")
	if d, ok := c.Model().(models.ClusterDetail); !ok || d.Cursor != 1 {
		t.Errorf("esc goes back to the detail, on gros-2: %T %+v", c.Model(), c.Model())
	}
}

func TestGOnTheClustersOpensTheReservations(t *testing.T) {
	c, _ := press(t, onClusters(t), "down") // gros
	c, cmd := press(t, c, "g")
	g, ok := c.Model().(models.Gantt)
	if !ok || g.Detail.Cluster.UID != "gros" || !c.loading || cmd == nil {
		t.Fatalf("g should open gros' time line and load it: %T loading=%v", c.Model(), c.loading)
	}
	c = run(t, c, cmd)
	if g = c.Model().(models.Gantt); g.Len() != 2 || c.loading {
		t.Fatalf("after load: %d nodes loading=%v", g.Len(), c.loading)
	}
	c, _ = press(t, c, "esc")
	if cl, ok := c.Model().(models.Clusters); !ok || cl.Site != "nancy" {
		t.Errorf("esc goes back to the clusters: %T", c.Model())
	}
}

func TestGanttKeys(t *testing.T) {
	c, _ := press(t, onDetail(t), "enter")
	g := func() models.Gantt { return c.Model().(models.Gantt) }
	steps := []struct {
		key  string
		test func() bool
	}{
		{"right", func() bool { return g().Col == 1 }},
		{"l", func() bool { return g().Col == 2 }},
		{"left", func() bool { return g().Col == 1 }},
		{"L", func() bool { return g().Col == 25 }}, // a day of hours
		{"n", func() bool { return g().Col == 0 }},
		{"-", func() bool { return g().Cell() == 2*time.Hour }},
		{"+", func() bool { return g().Cell() == time.Hour }},
		{"=", func() bool { return g().Cell() == 30*time.Minute }},
		{"down", func() bool { return g().Detail.Cursor == 1 }},
		{"k", func() bool { return g().Detail.Cursor == 0 }},
	}
	for _, s := range steps {
		c, _ = press(t, c, s.key)
		if !s.test() {
			t.Errorf("after %q: %+v", s.key, g())
		}
	}
	if _, cmd := press(t, c, "q"); cmd == nil {
		t.Error("q quits")
	}
}

func TestGanttReloadKeepsTheCursors(t *testing.T) {
	c, _ := press(t, onDetail(t), "down")
	c, _ = press(t, c, "enter")
	c, _ = press(t, c, "right")
	c, cmd := press(t, c, "r")
	if cmd == nil || !c.loading {
		t.Fatal("r reloads")
	}
	c = run(t, c, cmd)
	g, ok := c.Model().(models.Gantt)
	if !ok || g.Detail.Cursor != 1 || g.Col != 1 || c.loading {
		t.Errorf("after reload: %T %+v loading=%v", c.Model(), g, c.loading)
	}
}
