package controllers

import (
	"errors"
	"strings"
	"testing"

	"grid-tui/models"
)

// onClusters is a controller showing nancy's clusters (graffiti, gros).
func onClusters(t *testing.T) Controller {
	t.Helper()
	c, cmd := press(t, loaded(t), "enter")
	return run(t, c, cmd)
}

func TestEnterOpensTheSelectedCluster(t *testing.T) {
	c, _ := press(t, onClusters(t), "down") // gros
	c, cmd := press(t, c, "enter")

	d, ok := c.Model().(models.ClusterDetail)
	if !ok || d.Site != "nancy" || d.Cluster.UID != "gros" || d.Cluster.Model != "Dell PowerEdge R640" || !c.loading {
		t.Fatalf("enter should open gros and start loading: %T %+v loading=%v", c.Model(), c.Model(), c.loading)
	}
	if v := c.View(); !strings.Contains(v, "cluster: gros") || !strings.Contains(v, "loading") {
		t.Errorf("while loading:\n%s", v)
	}

	c = run(t, c, cmd)
	d = c.Model().(models.ClusterDetail)
	if c.loading || d.Len() != 2 || d.Nodes[0].Name != "gros-1" || d.At.IsZero() {
		t.Fatalf("after load: loading=%v %+v", c.loading, d)
	}
	v := c.View()
	for _, want := range []string{"cluster: gros", "nodes: 2", "MODEL       Dell PowerEdge R640", "gros-1", "/clusters/gros/status", "esc clusters"} {
		if !strings.Contains(v, want) {
			t.Errorf("view missing %q:\n%s", want, v)
		}
	}
}

func TestMoveSelectsANode(t *testing.T) {
	c, _ := press(t, onClusters(t), "down")
	c, cmd := press(t, c, "enter")
	c = run(t, c, cmd)
	c, _ = press(t, c, "down")
	if n, _ := c.Model().(models.ClusterDetail).Selected(); n.Name != "gros-2" {
		t.Errorf("selected = %q, want gros-2", n.Name)
	}
	if _, cmd := press(t, c, "enter"); cmd != nil {
		t.Error("enter on a node does nothing (yet)")
	}
}

func TestEscGoesBackToTheSameCluster(t *testing.T) {
	c, _ := press(t, onClusters(t), "down")
	c, cmd := press(t, c, "enter")
	c = run(t, c, cmd)
	c, _ = press(t, c, "esc")

	cl, ok := c.Model().(models.Clusters)
	if !ok || cl.Site != "nancy" {
		t.Fatalf("esc should show nancy's clusters, got %T", c.Model())
	}
	if sel, _ := cl.Selected(); sel.UID != "gros" {
		t.Errorf("selection after esc = %q, want gros", sel.UID)
	}
	c, _ = press(t, c, "esc")
	if _, ok := c.Model().(models.Sites); !ok {
		t.Errorf("esc again should show the sites, got %T", c.Model())
	}
}

func TestLateStatusIsDropped(t *testing.T) {
	c, cmd := press(t, onClusters(t), "enter") // graffiti, loading
	c, _ = press(t, c, "esc")
	c = run(t, c, cmd)
	if _, ok := c.Model().(models.Clusters); !ok || c.loading {
		t.Errorf("late status should be dropped: %T loading=%v", c.Model(), c.loading)
	}

	c, _ = press(t, c, "enter") // graffiti again
	next, _ := c.Update(DetailLoadedMsg{Site: "nancy", Cluster: "gros", Nodes: nodesByCluster["gros"]})
	if d := next.(Controller).Model().(models.ClusterDetail); d.Cluster.UID != "graffiti" || d.Len() != 0 {
		t.Errorf("gros nodes should not show on graffiti: %+v", d)
	}
}

func TestDetailErrorAndReload(t *testing.T) {
	var calls int32
	c := onClusters(t)
	c.client = fakeClient{err: errors.New("GET /sites/nancy/clusters/graffiti/status: 500"), calls: &calls}
	c, cmd := press(t, c, "enter")
	c = run(t, c, cmd)
	if v := c.View(); !strings.Contains(v, "error: GET /sites/nancy/clusters/graffiti/status: 500") {
		t.Errorf("the error should be on screen:\n%s", v)
	}

	c.client = fakeClient{nodes: nodesByCluster, calls: &calls}
	c, cmd = press(t, c, "r")
	c = run(t, c, cmd)
	// Each load is two calls: the status and the hardware.
	if d, ok := c.Model().(models.ClusterDetail); !ok || d.Cluster.UID != "graffiti" || d.Len() != 1 || c.err != nil || calls != 4 {
		t.Errorf("r should reload graffiti: %+v err=%v calls=%d", c.Model(), c.err, calls)
	}
}

func TestDetailLoadsTheHardware(t *testing.T) {
	c, _ := press(t, onClusters(t), "down") // gros
	c, cmd := press(t, c, "enter")
	c = run(t, c, cmd)
	if h := c.Model().(models.ClusterDetail).Hardware; h.CPU != "Intel Xeon Gold 5220" || h.Cores != 18 {
		t.Errorf("hardware = %+v", h)
	}
	if v := c.View(); !strings.Contains(v, "Intel Xeon Gold 5220") {
		t.Errorf("view should show the CPU:\n%s", v)
	}
}

func TestDetailKeepsWhatLoadedWhenOnePartFails(t *testing.T) {
	c, _ := press(t, onClusters(t), "down")
	c, _ = press(t, c, "enter")
	next, _ := c.Update(DetailLoadedMsg{
		Site: "nancy", Cluster: "gros",
		Nodes:       nodesByCluster["gros"],
		HardwareErr: errors.New("GET /sites/nancy/clusters/gros/nodes: 500"),
	})
	c = next.(Controller)
	d := c.Model().(models.ClusterDetail)
	if d.Len() != 2 || !d.Hardware.IsZero() || c.err == nil || c.loading {
		t.Errorf("nodes should be kept and the hardware error shown: %+v err=%v", d, c.err)
	}
}
