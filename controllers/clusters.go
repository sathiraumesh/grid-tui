package controllers

import (
	"context"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// The clusters of one site: loaded when enter opens the site and with r;
// enter opens the selected cluster (cluster.go); esc goes back to the sites.
//
//	enter / r ──▶ loadClusters ──runs──▶ client.Clusters ──▶ ClustersLoadedMsg ──▶ onClustersLoaded

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

// onClustersLoaded stores the clusters, if they are still the ones on
// screen: after esc, or for another site, they arrive too late and are
// dropped.
func (c Controller) onClustersLoaded(msg ClustersLoadedMsg) Controller {
	cur, ok := c.model.(models.Clusters)
	if !ok || cur.Site != msg.Site {
		return c
	}
	c.loading, c.err = false, msg.Err
	if msg.Err == nil {
		c.clusters = models.NewClusters(msg.Site, msg.Clusters)
		c.clusters.Cursor = cur.Cursor // a reload keeps the selection
		c.clusters = c.clusters.Move(0)
		c.model = c.clusters
	}
	return c
}
