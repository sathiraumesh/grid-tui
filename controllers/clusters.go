package controllers

import (
	"context"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// The clusters of one site: loaded when enter opens the site and with r;
// enter opens the selected cluster (cluster.go); esc goes back to the sites.
// Once the list is there, the hardware of every cluster loads at the same
// time, each filling its row when it arrives.
//
//	enter / r ──▶ loadClusters ──▶ client.Clusters ──▶ ClustersLoadedMsg ──▶ onClustersLoaded
//	                                                                            │ one per cluster
//	              onHardwareLoaded ◀── HardwareLoadedMsg ◀── client.ClusterHardware ◀┘

// ClustersLoadedMsg is what loadClusters sends when the call is done.
type ClustersLoadedMsg struct {
	Site     string // the site they were loaded for
	Clusters []models.Cluster
	Err      error
}

// loadClusters calls the API in the background.
func loadClusters(c Client, site string) tea.Cmd {
	return func() tea.Msg {
		clusters, err := c.Clusters(context.Background(), site)
		return ClustersLoadedMsg{Site: site, Clusters: clusters, Err: err}
	}
}

// HardwareLoadedMsg is what loadHardware sends for one cluster.
type HardwareLoadedMsg struct {
	Site, Cluster string
	Hardware      models.Hardware
	Err           error
}

// loadHardware calls the API for the hardware of one cluster in the background.
func loadHardware(c Client, site, cluster string) tea.Cmd {
	return func() tea.Msg {
		h, err := c.ClusterHardware(context.Background(), site, cluster)
		return HardwareLoadedMsg{Site: site, Cluster: cluster, Hardware: h, Err: err}
	}
}

// onClustersLoaded stores the clusters, if they are still the ones on
// screen (after esc, or for another site, they arrive too late and are
// dropped), and starts loading the hardware of each.
func (c Controller) onClustersLoaded(msg ClustersLoadedMsg) (Controller, tea.Cmd) {
	cur, ok := c.model.(models.Clusters)
	if !ok || cur.Site != msg.Site {
		return c, nil
	}
	c.loading, c.err = false, msg.Err
	if msg.Err != nil {
		return c, nil
	}
	c.clusters = models.NewClusters(msg.Site, msg.Clusters)
	c.clusters.Cursor = cur.Cursor // a reload keeps the selection
	c.clusters = c.clusters.Move(0)
	c.model = c.clusters

	loads := make([]tea.Cmd, 0, len(msg.Clusters))
	for _, cl := range msg.Clusters {
		loads = append(loads, loadHardware(c.client, msg.Site, cl.UID))
	}
	return c, tea.Batch(loads...)
}

// onHardwareLoaded fills in one cluster's row. It is kept while the
// detail of a cluster is shown, so esc finds it there; for another site
// it is dropped. A failure shows on that row only.
func (c Controller) onHardwareLoaded(msg HardwareLoadedMsg) Controller {
	if c.clusters.Site != msg.Site {
		return c
	}
	c.clusters = c.clusters.WithHardware(msg.Cluster, msg.Hardware, msg.Err == nil)
	if cur, ok := c.model.(models.Clusters); ok && cur.Site == msg.Site {
		c.model = c.clusters
	}
	return c
}
