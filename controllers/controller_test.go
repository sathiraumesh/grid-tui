package controllers

import (
	"context"
	"sync/atomic"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
	"grid-tui/views"
)

// fakeClient answers with fixed data, or err; calls counts the loads.
type fakeClient struct {
	sites    []models.Site
	clusters map[string][]models.Cluster
	nodes    map[string][]models.NodeStatus // by cluster
	hardware map[string]models.Hardware     // by cluster
	err      error
	calls    *int32 // atomic: the detail's two calls run at the same time
}

func (f fakeClient) count() {
	if f.calls != nil {
		atomic.AddInt32(f.calls, 1)
	}
}

func (f fakeClient) Sites(context.Context) ([]models.Site, error) {
	f.count()
	return f.sites, f.err
}

func (f fakeClient) Clusters(_ context.Context, site string) ([]models.Cluster, error) {
	f.count()
	return f.clusters[site], f.err
}

func (f fakeClient) ClusterStatus(_ context.Context, _, cluster string) ([]models.NodeStatus, error) {
	f.count()
	return f.nodes[cluster], f.err
}

func (f fakeClient) ClusterHardware(_ context.Context, _, cluster string) (models.Hardware, error) {
	f.count()
	return f.hardware[cluster], f.err
}

var twoSites = []models.Site{
	{UID: "nancy", Name: "Nancy", Description: "Grid5000 Nancy site"},
	{UID: "rennes", Name: "Rennes", Description: "Grid5000 Rennes site"},
}

var clustersBySite = map[string][]models.Cluster{
	"nancy":  {{UID: "graffiti", Model: "Dell PowerEdge T640"}, {UID: "gros", Model: "Dell PowerEdge R640"}},
	"rennes": {{UID: "paravance", Model: "Dell PowerEdge R630"}},
}

var nodesByCluster = map[string][]models.NodeStatus{
	"gros":     {{Name: "gros-2", Hard: "alive", Soft: "free"}, {Name: "gros-1", Hard: "alive", Soft: "free"}},
	"graffiti": {{Name: "graffiti-1", Hard: "dead", Soft: "unknown"}},
}

var hardwareByCluster = map[string]models.Hardware{
	"gros":      {Nodes: 2, CPU: "Intel Xeon Gold 5220", Sockets: 1, Cores: 18, Threads: 36, MemoryBytes: 96 << 30},
	"graffiti":  {Nodes: 1, CPU: "Intel Xeon Silver 4110", Sockets: 2, Cores: 16, MemoryBytes: 128 << 30},
	"paravance": {Nodes: 72, CPU: "Intel Xeon E5-2630 v3", Sockets: 2, Cores: 16, MemoryBytes: 128 << 30},
}

var working = fakeClient{sites: twoSites, clusters: clustersBySite, nodes: nodesByCluster, hardware: hardwareByCluster}

// sized gives the controller a 100×24 terminal.
func sized(t *testing.T, c Controller) Controller {
	t.Helper()
	next, _ := c.Update(tea.WindowSizeMsg{Width: 100, Height: 24})
	return next.(Controller)
}

// run runs cmd, as Bubble Tea would, and feeds its message back to Update.
func run(t *testing.T, c Controller, cmd tea.Cmd) Controller {
	t.Helper()
	if cmd == nil {
		t.Fatal("expected a command")
	}
	next, _ := c.Update(cmd())
	return next.(Controller)
}

// press sends one key and returns the controller and the command it started.
func press(t *testing.T, c Controller, k string) (Controller, tea.Cmd) {
	t.Helper()
	msg := tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(k)}
	switch k {
	case "enter":
		msg = tea.KeyMsg{Type: tea.KeyEnter}
	case "esc":
		msg = tea.KeyMsg{Type: tea.KeyEsc}
	case "up":
		msg = tea.KeyMsg{Type: tea.KeyUp}
	case "down":
		msg = tea.KeyMsg{Type: tea.KeyDown}
	case "left":
		msg = tea.KeyMsg{Type: tea.KeyLeft}
	case "right":
		msg = tea.KeyMsg{Type: tea.KeyRight}
	case "backspace":
		msg = tea.KeyMsg{Type: tea.KeyBackspace}
	case " ":
		msg = tea.KeyMsg{Type: tea.KeySpace, Runes: []rune(" ")}
	}
	next, cmd := c.Update(msg)
	return next.(Controller), cmd
}

// loaded is a controller on a 100×24 terminal with the two sites loaded.
func loaded(t *testing.T) Controller {
	t.Helper()
	c := sized(t, New(working))
	return run(t, c, c.Init())
}

func TestNoClient(t *testing.T) {
	c := sized(t, New(nil))
	if c.Init() != nil {
		t.Error("no client: nothing to load")
	}
	for _, k := range []string{"r", "enter"} {
		if _, cmd := press(t, c, k); cmd != nil {
			t.Errorf("no client: %s does nothing", k)
		}
	}
}

func TestResizeStoresTheSize(t *testing.T) {
	if w, h := sized(t, New(nil)).Size(); w != 100 || h != 24 {
		t.Errorf("size = %dx%d, want 100x24", w, h)
	}
}

func TestQuit(t *testing.T) {
	for _, k := range []tea.KeyMsg{{Type: tea.KeyRunes, Runes: []rune("q")}, {Type: tea.KeyCtrlC}} {
		_, cmd := sized(t, New(nil)).Update(k)
		if cmd == nil {
			t.Fatalf("%s should quit", k)
		}
		if _, ok := cmd().(tea.QuitMsg); !ok {
			t.Fatalf("%s should return tea.Quit", k)
		}
	}
}

func TestScrollSideways(t *testing.T) {
	c, cmd := press(t, loaded(t), "enter") // nancy's clusters: a wide table
	c = run(t, c, cmd)
	narrow, _ := c.Update(tea.WindowSizeMsg{Width: 50, Height: 24})
	c = narrow.(Controller)

	c, _ = press(t, c, "right")
	if c.scrollX != scrollStep {
		t.Fatalf("→: scrollX = %d, want %d", c.scrollX, scrollStep)
	}
	c, _ = press(t, c, "h")
	if c.scrollX != 0 {
		t.Errorf("h: scrollX = %d, want 0", c.scrollX)
	}
	c, _ = press(t, c, "left")
	if c.scrollX != 0 {
		t.Errorf("can't scroll past the left edge: %d", c.scrollX)
	}
	for range 100 {
		c, _ = press(t, c, "l")
	}
	if want := views.MaxScrollX(views.For(c.Model()), 50); c.scrollX != want || want == 0 {
		t.Errorf("should stop at the widest line's end: scrollX = %d, want %d", c.scrollX, want)
	}

	// A wider terminal needs less scrolling.
	wide, _ := c.Update(tea.WindowSizeMsg{Width: 400, Height: 24})
	if wide.(Controller).scrollX != 0 {
		t.Errorf("everything fits at 400 columns: scrollX = %d", wide.(Controller).scrollX)
	}

	// Going back starts the sites at their left edge.
	c, _ = press(t, c, "esc")
	if c.scrollX != 0 {
		t.Errorf("esc: scrollX = %d, want 0", c.scrollX)
	}
}

func TestOpeningAScreenStartsAtTheLeft(t *testing.T) {
	c, cmd := press(t, loaded(t), "enter")
	c = run(t, c, cmd)
	narrow, _ := c.Update(tea.WindowSizeMsg{Width: 50, Height: 24})
	c, _ = press(t, narrow.(Controller), "right")
	c, _ = press(t, c, "enter") // open a cluster
	if c.scrollX != 0 {
		t.Errorf("a new screen should start at the left: %d", c.scrollX)
	}
}
