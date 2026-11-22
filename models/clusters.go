package models

// Cluster is one cluster of a site, as GET /sites/{site}/clusters lists it.
type Cluster struct {
	UID    string   // e.g. "gros": used in every API path
	Model  string   // the hardware, e.g. "Dell PowerEdge R640"
	Queues []string // OAR queues it is in, e.g. ["default", "admin"]
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
