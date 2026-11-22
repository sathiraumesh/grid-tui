package views

import (
	"slices"
	"strings"
	"testing"

	"grid-tui/models"
)

// sampleClusters are made-up rows for tests only.
func sampleClusters() models.Clusters {
	c := models.NewClusters("nancy", []models.Cluster{
		{UID: "graffiti", Model: "Dell PowerEdge T640", Queues: []string{"production", "admin"}},
		{UID: "gros", Model: "Dell PowerEdge R640", Queues: []string{"default", "admin"},
			Metrics: []models.Metric{{Name: "wattmetre_power_watt"}}},
		{UID: "grouille", Model: "Dell PowerEdge R7525"},
	})
	c = c.WithHardware("gros", models.Hardware{
		Nodes: 124, CPU: "Intel Xeon Gold 5220", Sockets: 1, Cores: 18, MemoryBytes: 96 << 30,
		Disks: []models.Disk{{Kind: "SSD", Interface: "SATA", Bytes: 480e9}},
		NICs:  []models.NIC{{Interface: "Ethernet", RateBps: 25e9}},
	}, true)
	return c.WithHardware("grouille", models.Hardware{}, false)
}

func TestClustersViewTable(t *testing.T) {
	v := ClustersView{Clusters: sampleClusters()}
	want := []string{
		"CLUSTER    NODES   CPU                        CORES   MEMORY   GPU   STORAGE           NETWORK            WATTMETER",
		"graffiti   …       …                          …       …        …     …                 …                  no",
		"gros       124     1 × Intel Xeon Gold 5220   18      96 GiB   -     480 GB SSD SATA   25 Gbps Ethernet   yes",
		"grouille   ?       ?                          ?       ?        ?     ?                 ?                  no",
	}
	if got := v.Lines(); !slices.Equal(got, want) {
		t.Errorf("Lines =\n%s\nwant\n%s", strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
	if got := v.Labels(); !slices.Equal(got, []string{"site: nancy", "clusters: 3"}) {
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
