package views

import (
	"strconv"
	"strings"

	"grid-tui/models"
)

// ClustersView draws the clusters of one site, the selected one highlighted:
//
//	┌─   site: nancy   ───   clusters: 2   ──────────────────────────┐
//	│                                                                │
//	│ CLUSTER    MODEL                 QUEUES                        │
//	│ graffiti   Dell PowerEdge T640   production, admin             │  ◀ selected
//	│ gros       Dell PowerEdge R640   default, admin                │
//	└─ $ curl https://api.grid5000.fr/stable/sites/nancy/clusters ───┘
type ClustersView struct {
	Clusters models.Clusters
}

var _ Selectable = ClustersView{} // ClustersView implements Selectable (and View)

var clusterColumns = []string{"CLUSTER", "MODEL", "QUEUES"}

func (v ClustersView) Labels() []string {
	return []string{"site: " + v.Clusters.Site, "clusters: " + strconv.Itoa(v.Clusters.Len())}
}

func (v ClustersView) Command() string {
	return "curl https://api.grid5000.fr/stable/sites/" + v.Clusters.Site + "/clusters"
}

func (v ClustersView) Help() string {
	return "↑↓ move • esc sites • r reload • q quit"
}

// Lines is the clusters as a table, or none while there are none (or they
// are still loading).
func (v ClustersView) Lines() []string {
	if v.Clusters.Len() == 0 {
		return nil
	}
	rows := make([][]string, 0, v.Clusters.Len())
	for _, c := range v.Clusters.Items {
		rows = append(rows, []string{c.UID, c.Model, strings.Join(c.Queues, ", ")})
	}
	return table(clusterColumns, rows)
}

// Selected is the selected cluster's line: under the header row.
func (v ClustersView) Selected() int {
	if v.Clusters.Len() == 0 {
		return -1
	}
	return v.Clusters.Cursor + 1
}
