package views

import (
	"slices"
	"strings"
	"testing"

	"grid-tui/models"
)

// sampleClusters are made-up rows for tests only.
func sampleClusters() models.Clusters {
	return models.NewClusters("nancy", []models.Cluster{
		{UID: "graffiti", Model: "Dell PowerEdge T640", Queues: []string{"production", "admin"}},
		{UID: "gros", Model: "Dell PowerEdge R640", Queues: []string{"default", "admin"}},
	})
}

func TestClustersViewTable(t *testing.T) {
	v := ClustersView{Clusters: sampleClusters()}
	want := []string{
		"CLUSTER    MODEL                 QUEUES",
		"graffiti   Dell PowerEdge T640   production, admin",
		"gros       Dell PowerEdge R640   default, admin",
	}
	if got := v.Lines(); !slices.Equal(got, want) {
		t.Errorf("Lines =\n%s\nwant\n%s", strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
	if got := v.Labels(); !slices.Equal(got, []string{"site: nancy", "clusters: 2"}) {
		t.Errorf("Labels = %q", got)
	}
	if got := v.Command(); got != "curl https://api.grid5000.fr/stable/sites/nancy/clusters" {
		t.Errorf("Command = %q", got)
	}
	if !strings.Contains(v.Help(), "enter details") || !strings.Contains(v.Help(), "esc sites") {
		t.Errorf("Help = %q", v.Help())
	}
}

func TestClustersViewSelected(t *testing.T) {
	v := ClustersView{Clusters: sampleClusters().Move(1)}
	if got := v.Lines()[v.Selected()]; !strings.HasPrefix(got, "gros") {
		t.Errorf("selected line = %q, want the gros row", got)
	}
}

func TestClustersViewLoading(t *testing.T) {
	v := ClustersView{Clusters: models.NewClusters("nancy", nil)}
	s := Render(v, Status{Loading: true}, 100, 24)
	for _, want := range []string{"site: nancy", "clusters: 0", emptyText, "loading…"} {
		if !strings.Contains(s, want) {
			t.Errorf("loading clusters: missing %q:\n%s", want, s)
		}
	}
	if v.Selected() != -1 {
		t.Error("no clusters: nothing selected")
	}
}
