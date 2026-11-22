package controllers

import (
	"context"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// The clusters of one site: loaded when enter opens the site and with r;
// esc goes back to the sites.
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
		c.model = models.NewClusters(msg.Site, msg.Clusters)
	}
	return c
}

// back returns from the clusters to the sites, on the same row.
func (c Controller) back() Controller {
	if _, onClusters := c.model.(models.Clusters); onClusters {
		c.model = c.sites
		c.loading, c.err = false, nil // a clusters load still on its way is dropped
	}
	return c
}
