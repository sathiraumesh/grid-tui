package controllers

import (
	"errors"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

func TestEnterLoadsTheClustersOfTheSelectedSite(t *testing.T) {
	c, _ := press(t, loaded(t), "down") // rennes
	c, cmd := press(t, c, "enter")

	cl, ok := c.Model().(models.Clusters)
	if !ok || cl.Site != "rennes" || !c.loading {
		t.Fatalf("enter should open rennes and start loading: %T %+v loading=%v", c.Model(), c.Model(), c.loading)
	}
	if v := c.View(); !strings.Contains(v, "site: rennes") || !strings.Contains(v, "loading") {
		t.Errorf("while loading:\n%s", v)
	}

	c = run(t, c, cmd)
	if c.loading || c.Model().Len() != 1 {
		t.Fatalf("after load: loading=%v Len=%d", c.loading, c.Model().Len())
	}
	v := c.View()
	for _, want := range []string{"site: rennes", "clusters: 1", "paravance", "…", "/sites/rennes/clusters", "esc sites"} {
		if !strings.Contains(v, want) {
			t.Errorf("view missing %q:\n%s", want, v)
		}
	}
}

func TestEscGoesBackToTheSameSite(t *testing.T) {
	c, _ := press(t, loaded(t), "down")
	c, cmd := press(t, c, "enter")
	c = run(t, c, cmd)
	c, _ = press(t, c, "esc")

	s, ok := c.Model().(models.Sites)
	if !ok {
		t.Fatalf("esc should show the sites, got %T", c.Model())
	}
	if site, _ := s.Selected(); site.UID != "rennes" {
		t.Errorf("selection after esc = %q, want rennes", site.UID)
	}
}

func TestMoveSelectsACluster(t *testing.T) {
	c, cmd := press(t, loaded(t), "enter") // nancy: graffiti, gros
	c = run(t, c, cmd)
	c, _ = press(t, c, "down")
	if cur := c.Model().(models.Clusters).Cursor; cur != 1 {
		t.Errorf("Cursor = %d, want 1", cur)
	}
}

func TestLateClustersAreDropped(t *testing.T) {
	c, cmd := press(t, loaded(t), "enter") // nancy, loading
	c, _ = press(t, c, "esc")              // back before they arrive
	c = run(t, c, cmd)
	if _, ok := c.Model().(models.Sites); !ok || c.loading {
		t.Errorf("late clusters should be dropped: %T loading=%v", c.Model(), c.loading)
	}

	// Clusters of another site than the one on screen are dropped too.
	c, _ = press(t, c, "enter") // nancy
	next, _ := c.Update(ClustersLoadedMsg{Site: "rennes", Clusters: clustersBySite["rennes"]})
	if cl := next.(Controller).Model().(models.Clusters); cl.Site != "nancy" || cl.Len() != 0 {
		t.Errorf("rennes clusters should not show on nancy: %+v", cl)
	}
}

func TestClustersErrorAndReload(t *testing.T) {
	var calls int32
	c := loaded(t)
	c.client = fakeClient{err: errors.New("GET /sites/nancy/clusters: 500"), calls: &calls}
	c, cmd := press(t, c, "enter")
	c = run(t, c, cmd)
	if v := c.View(); !strings.Contains(v, "error: GET /sites/nancy/clusters: 500") {
		t.Errorf("the error should be on screen:\n%s", v)
	}

	c.client = fakeClient{clusters: clustersBySite, calls: &calls}
	c, cmd = press(t, c, "r")
	c = run(t, c, cmd)
	if cl, ok := c.Model().(models.Clusters); !ok || cl.Site != "nancy" || cl.Len() != 2 || c.err != nil || calls != 2 {
		t.Errorf("r should reload nancy's clusters: %+v err=%v calls=%d", c.Model(), c.err, calls)
	}
}

func TestClustersLoadTheirHardware(t *testing.T) {
	c, cmd := press(t, loaded(t), "enter") // nancy: graffiti, gros
	next, hwCmd := c.Update(cmd())         // the clusters arrive and start the hardware loads
	c = next.(Controller)
	if hwCmd == nil {
		t.Fatal("the clusters should start loading their hardware")
	}
	batch, ok := hwCmd().(tea.BatchMsg)
	if !ok || len(batch) != 2 {
		t.Fatalf("want one hardware load per cluster, got %T %v", hwCmd(), batch)
	}
	for _, load := range batch {
		next, _ = c.Update(load())
		c = next.(Controller)
	}
	cl := c.Model().(models.Clusters)
	if gros := cl.Items[1]; gros.HardwareState != models.HardwareLoaded || gros.Hardware.CPU != "Intel Xeon Gold 5220" {
		t.Errorf("gros = %+v", gros)
	}
	if v := c.View(); !strings.Contains(v, "1 × Intel Xeon Gold 5220") || !strings.Contains(v, "96 GiB") {
		t.Errorf("the gros row should show its hardware:\n%s", v)
	}
}

func TestHardwareForAnotherSiteIsDropped(t *testing.T) {
	c, cmd := press(t, loaded(t), "enter") // nancy
	c = run(t, c, cmd)
	next, _ := c.Update(HardwareLoadedMsg{Site: "rennes", Cluster: "gros", Hardware: models.Hardware{CPU: "x"}})
	if gros := next.(Controller).Model().(models.Clusters).Items[1]; gros.HardwareState != models.HardwareLoading {
		t.Errorf("hardware for rennes should not fill nancy's gros: %+v", gros)
	}
}
