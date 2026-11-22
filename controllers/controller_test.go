package controllers

import (
	"context"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// fakeClient answers with fixed data, or err; calls counts the loads.
type fakeClient struct {
	sites    []models.Site
	clusters map[string][]models.Cluster
	err      error
	calls    *int
}

func (f fakeClient) count() {
	if f.calls != nil {
		*f.calls++
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

var twoSites = []models.Site{
	{UID: "nancy", Name: "Nancy", Description: "Grid5000 Nancy site"},
	{UID: "rennes", Name: "Rennes", Description: "Grid5000 Rennes site"},
}

var clustersBySite = map[string][]models.Cluster{
	"nancy":  {{UID: "graffiti", Model: "Dell PowerEdge T640"}, {UID: "gros", Model: "Dell PowerEdge R640"}},
	"rennes": {{UID: "paravance", Model: "Dell PowerEdge R630"}},
}

var working = fakeClient{sites: twoSites, clusters: clustersBySite}

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
