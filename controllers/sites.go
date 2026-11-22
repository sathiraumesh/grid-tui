package controllers

import (
	"context"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// The list of sites: loaded at start and with r; enter opens the selected
// site's clusters.
//
//	Init / r ──▶ loadSites ──runs──▶ client.Sites ──▶ SitesLoadedMsg ──▶ onSitesLoaded

// SitesLoadedMsg is what loadSites sends when the call is done.
type SitesLoadedMsg struct {
	Sites []models.Site
	Err   error
}

// loadSites calls the API in the background.
func loadSites(c Client) tea.Cmd {
	return func() tea.Msg {
		sites, err := c.Sites(context.Background())
		return SitesLoadedMsg{Sites: sites, Err: err}
	}
}

// onSitesLoaded stores the sites, keeping the selection inside the list.
// If clusters are on screen, the sites are kept for when esc goes back.
func (c Controller) onSitesLoaded(msg SitesLoadedMsg) Controller {
	if msg.Err == nil {
		c.sites = c.sites.WithItems(msg.Sites)
	}
	if _, onSites := c.model.(models.Sites); onSites {
		c.model = c.sites
		c.loading, c.err = false, msg.Err
	}
	return c
}

// openSite shows the clusters of the selected site and starts loading them.
func (c Controller) openSite() (tea.Model, tea.Cmd) {
	if _, onSites := c.model.(models.Sites); !onSites || c.client == nil || c.loading {
		return c, nil
	}
	site, ok := c.sites.Selected()
	if !ok {
		return c, nil
	}
	c.clusters = models.NewClusters(site.UID, nil)
	c.model = c.clusters
	c.loading, c.err = true, nil
	return c, loadClusters(c.client, site.UID)
}
