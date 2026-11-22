package models

import "strings"

// Cluster is one cluster of a site, as GET /sites/{site}/clusters lists it,
// plus its hardware once that is loaded.
type Cluster struct {
	UID     string   // e.g. "gros": used in every API path
	Model   string   // the hardware, e.g. "Dell PowerEdge R640"
	Queues  []string // OAR queues it is in, e.g. ["default", "admin"]
	Metrics []Metric // what Kwollect can measure on its nodes

	Hardware      Hardware      // what one node is made of
	HardwareState HardwareState // whether Hardware is loaded yet
}

// HardwareState is whether a cluster's hardware has been loaded.
type HardwareState int

const (
	HardwareLoading HardwareState = iota
	HardwareLoaded
	HardwareFailed
)

// Metric is one measure Kwollect (Grid'5000's monitoring) collects on a
// cluster's nodes, e.g. "wattmetre_power_watt".
type Metric struct {
	Name        string
	Description string
	PeriodMs    int  // how often it is measured, in milliseconds
	Optional    bool // only collected when a job asks for it
}

// Wattmeter is whether the cluster's nodes have a wattmeter: Kwollect has
// a wattmetre_* metric for them.
func (c Cluster) Wattmeter() bool {
	for _, m := range c.Metrics {
		if strings.HasPrefix(m.Name, "wattmetre") {
			return true
		}
	}
	return false
}

// Clusters is the list of clusters of one site and which one is selected.
type Clusters struct {
	Site   string // the site's UID, e.g. "nancy"
	Items  []Cluster
	Cursor int // index of the selected cluster
}

var _ Model = Clusters{} // Clusters implements Model

// NewClusters makes the model of the clusters of site, the first one
// selected. items may be nil while they are loading.
func NewClusters(site string, items []Cluster) Clusters {
	return Clusters{Site: site, Items: items}
}

// Len is how many clusters there are.
func (c Clusters) Len() int { return len(c.Items) }

// Move moves the selection by step (negative is up), within the list.
func (c Clusters) Move(step int) Clusters {
	c.Cursor = moveCursor(c.Cursor, step, len(c.Items))
	return c
}

// Selected is the selected cluster, or false if there are none.
func (c Clusters) Selected() (Cluster, bool) {
	if c.Cursor < 0 || c.Cursor >= len(c.Items) {
		return Cluster{}, false
	}
	return c.Items[c.Cursor], true
}

// WithHardware stores the hardware of cluster uid (failed if !ok). The
// list is copied: other copies of the model keep theirs.
func (c Clusters) WithHardware(uid string, h Hardware, ok bool) Clusters {
	items := make([]Cluster, len(c.Items))
	copy(items, c.Items)
	for i := range items {
		if items[i].UID == uid {
			items[i].Hardware, items[i].HardwareState = h, HardwareLoaded
			if !ok {
				items[i].Hardware, items[i].HardwareState = Hardware{}, HardwareFailed
			}
		}
	}
	c.Items = items
	return c
}
