package controllers

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// searching opens the search on the loaded sites and runs every site's
// load, as Bubble Tea would.
func searching(t *testing.T) Controller {
	t.Helper()
	c, cmd := press(t, loaded(t), "/")
	if _, ok := c.Model().(models.Search); !ok {
		t.Fatalf("/ should open the search, got %T", c.Model())
	}
	batch, ok := cmd().(tea.BatchMsg)
	if !ok || len(batch) != len(twoSites) {
		t.Fatalf("want one load per site, got %v", batch)
	}
	for _, load := range batch {
		next, _ := c.Update(load())
		c = next.(Controller)
	}
	return c
}

// focus moves the search's focus to the field with key.
func focus(t *testing.T, c Controller, key string) Controller {
	t.Helper()
	for range len(models.SearchFields) + 10 {
		c, _ = press(t, c, "up") // to the first field
	}
	for i, f := range models.SearchFields {
		if f.Key == key {
			for range i {
				c, _ = press(t, c, "down")
			}
			return c
		}
	}
	t.Fatalf("no field %q", key)
	return c
}

func results(c Controller) []string {
	var out []string
	for _, e := range c.Model().(models.Search).Results() {
		out = append(out, e.Site+"/"+e.Cluster.UID)
	}
	return out
}

func TestSearchLoadsEverySite(t *testing.T) {
	c := searching(t)
	s := c.Model().(models.Search)
	if s.Loading() || len(s.Entries) != 3 { // nancy: graffiti, gros; rennes: paravance
		t.Fatalf("entries = %+v loading=%v", s.Entries, s.Loading())
	}
	if gros := s.Entries[1]; gros.Cluster.UID != "gros" || gros.Cluster.HardwareState != models.HardwareLoaded || gros.Cluster.Hardware.Cores != 18 {
		t.Errorf("gros = %+v", gros)
	}
	if v := c.View(); !strings.Contains(v, "matches: 3 of 3") {
		t.Errorf("view:\n%s", v)
	}
}

func TestSearchFormKeys(t *testing.T) {
	c := focus(t, searching(t), "cores")
	c, _ = press(t, c, "1")
	c, _ = press(t, c, "x") // not a digit: ignored
	c, _ = press(t, c, "8")
	if got := results(c); len(got) != 1 || got[0] != "nancy/gros" {
		t.Errorf("cores >= 18: %v", got)
	}
	c, _ = press(t, c, "backspace") // 1
	c, _ = press(t, c, "backspace") // empty: any
	if got := results(c); len(got) != 3 {
		t.Errorf("no minimum: %v", got)
	}

	c = focus(t, c, "site")
	c, _ = press(t, c, "enter") // next option: nancy
	if got := results(c); len(got) != 2 {
		t.Errorf("site nancy: %v", got)
	}
	c, _ = press(t, c, "right") // rennes
	if got := results(c); len(got) != 1 || got[0] != "rennes/paravance" {
		t.Errorf("site rennes: %v", got)
	}
	c, _ = press(t, c, "left") // nancy again
	c, _ = press(t, c, "left") // any
	if got := results(c); len(got) != 3 {
		t.Errorf("site any: %v", got)
	}

	c = focus(t, c, "hasgpu")
	c, _ = press(t, c, " ")
	if got := results(c); len(got) != 0 {
		t.Errorf("no cluster has a GPU here: %v", got)
	}
	if v := c.View(); !strings.Contains(v, "no cluster meets these requirements") {
		t.Errorf("view:\n%s", v)
	}
	c, _ = press(t, c, "enter") // untick
	if got := results(c); len(got) != 3 {
		t.Errorf("unticked: %v", got)
	}
}

func TestSearchKeysAreNotTheOtherScreens(t *testing.T) {
	c := focus(t, searching(t), "cores")
	c, cmd := press(t, c, "q")
	if cmd == nil {
		t.Fatal("q still quits")
	}
	c, _ = press(t, c, "/")
	if _, ok := c.Model().(models.Search); !ok {
		t.Error("/ on the search does nothing")
	}
}

func TestSearchResultOpensItsDetailAndEscComesBack(t *testing.T) {
	c := focus(t, searching(t), "cores")
	c, _ = press(t, c, "1")
	c, _ = press(t, c, "8") // only gros
	for range len(models.SearchFields) {
		c, _ = press(t, c, "down") // down into the results
	}
	c, cmd := press(t, c, "enter")
	d, ok := c.Model().(models.ClusterDetail)
	if !ok || d.Site != "nancy" || d.Cluster.UID != "gros" {
		t.Fatalf("enter on a result should open gros: %T %+v", c.Model(), c.Model())
	}
	c = run(t, c, cmd)
	if c.Model().Len() != 2 {
		t.Errorf("gros' nodes should load: %d", c.Model().Len())
	}

	c, _ = press(t, c, "esc")
	s, ok := c.Model().(models.Search)
	if !ok {
		t.Fatalf("esc should go back to the search, got %T", c.Model())
	}
	if got := results(c); len(got) != 1 || s.Value(7) != "18" {
		t.Errorf("the requirements should be kept: %v %q", got, s.Value(7))
	}

	c, _ = press(t, c, "esc")
	if _, ok := c.Model().(models.Sites); !ok {
		t.Errorf("esc again: the sites, got %T", c.Model())
	}
	c, cmd = press(t, c, "/")
	if cmd != nil || c.Model().(models.Search).Len() != 1 {
		t.Error("opening the search again keeps what was loaded and set")
	}
}

func TestSearchNeedsTheSites(t *testing.T) {
	c := sized(t, New(working)) // the sites are still loading
	if _, cmd := press(t, c, "/"); cmd != nil {
		t.Error("/ before the sites are there does nothing")
	}
}

func TestSearchReload(t *testing.T) {
	c := searching(t)
	c, cmd := press(t, c, "r")
	s := c.Model().(models.Search)
	if cmd == nil || !s.Loading() || len(s.Entries) != 3 {
		t.Errorf("r should load every site again, keeping the results meanwhile: loading=%v entries=%d", s.Loading(), len(s.Entries))
	}
	if _, again := press(t, c, "r"); again != nil {
		t.Error("r while loading does nothing")
	}
}
