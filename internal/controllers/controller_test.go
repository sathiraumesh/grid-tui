package controllers

import (
	"context"
	"errors"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/internal/models"
)

// fakeClient returns fixed sites, or err; calls counts the loads.
type fakeClient struct {
	sites []models.Site
	err   error
	calls *int
}

func (f fakeClient) Sites(context.Context) ([]models.Site, error) {
	if f.calls != nil {
		*f.calls++
	}
	return f.sites, f.err
}

var twoSites = []models.Site{
	{UID: "nancy", Name: "Nancy", Description: "Grid5000 Nancy site"},
	{UID: "rennes", Name: "Rennes", Description: "Grid5000 Rennes site"},
}

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

func key(k string) tea.KeyMsg { return tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune(k)} }

func TestLoadsTheSitesAtStart(t *testing.T) {
	c := sized(t, New(fakeClient{sites: twoSites}))
	if v := c.View(); !strings.Contains(v, "loading") {
		t.Errorf("before the sites arrive it should say loading:\n%s", v)
	}

	c = run(t, c, c.Init())
	if c.Model().Len() != 2 {
		t.Fatalf("Len = %d, want 2", c.Model().Len())
	}
	v := c.View()
	for _, want := range []string{"sites: 2", "nancy", "Grid5000 Rennes site", "r reload"} {
		if !strings.Contains(v, want) {
			t.Errorf("view missing %q:\n%s", want, v)
		}
	}
	if strings.Contains(v, "loading") {
		t.Errorf("loading should be gone:\n%s", v)
	}
}

func TestLoadErrorIsShownAndReloadRetries(t *testing.T) {
	calls := 0
	failing := fakeClient{err: errors.New("GET /sites: 401 Unauthorized"), calls: &calls}
	c := sized(t, New(failing))
	c = run(t, c, c.Init())
	if v := c.View(); !strings.Contains(v, "401 Unauthorized") {
		t.Errorf("the error should be on screen:\n%s", v)
	}

	// r reloads, now with a client that works.
	c.client = fakeClient{sites: twoSites, calls: &calls}
	next, cmd := c.Update(key("r"))
	c = next.(Controller)
	if !c.loading || c.err != nil {
		t.Errorf("r should start loading and clear the error")
	}
	c = run(t, c, cmd)
	if c.Model().Len() != 2 || c.err != nil || calls != 2 {
		t.Errorf("after reload: Len=%d err=%v calls=%d", c.Model().Len(), c.err, calls)
	}
}

func TestErrorKeepsTheOldSites(t *testing.T) {
	c := sized(t, New(fakeClient{sites: twoSites}))
	c = run(t, c, c.Init())
	next, _ := c.Update(SitesLoadedMsg{Err: errors.New("timeout")})
	if c = next.(Controller); c.Model().Len() != 2 {
		t.Errorf("a failed reload should keep the sites, Len=%d", c.Model().Len())
	}
}

func TestReloadWhileLoadingDoesNothing(t *testing.T) {
	c := sized(t, New(fakeClient{sites: twoSites})) // loading since New
	if _, cmd := c.Update(key("r")); cmd != nil {
		t.Error("r while loading should not start a second load")
	}
}

func TestNoClient(t *testing.T) {
	c := sized(t, New(nil))
	if c.Init() != nil {
		t.Error("no client: nothing to load")
	}
	if _, cmd := c.Update(key("r")); cmd != nil {
		t.Error("no client: r does nothing")
	}
	if v := c.View(); !strings.Contains(v, "sites: 0") || strings.Contains(v, "loading") {
		t.Errorf("no client view:\n%s", v)
	}
}

func TestResizeStoresTheSize(t *testing.T) {
	if w, h := sized(t, New(nil)).Size(); w != 100 || h != 24 {
		t.Errorf("size = %dx%d, want 100x24", w, h)
	}
}

func TestQuit(t *testing.T) {
	for _, k := range []tea.KeyMsg{key("q"), {Type: tea.KeyCtrlC}} {
		_, cmd := sized(t, New(nil)).Update(k)
		if cmd == nil {
			t.Fatalf("%s should quit", k)
		}
		if _, ok := cmd().(tea.QuitMsg); !ok {
			t.Fatalf("%s should return tea.Quit", k)
		}
	}
}
