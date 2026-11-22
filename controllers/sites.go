package controllers

import (
	"context"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// Loading the sites. Calling the API can take seconds, so it never runs in
// Update: Update returns a command, Bubble Tea runs it in the background,
// and its result comes back to Update as a message.
//
//	Init / r ──▶ loadSites(client) ──runs──▶ client.Sites
//	                                              │
//	              Update ◀── SitesLoadedMsg ──────┘
//	                │
//	                └─▶ model = models.NewSites(msg.Sites) ──▶ View draws it

// SitesClient is what loads the sites: *grid5000.Client in the app, a fake
// in tests.
type SitesClient interface {
	Sites(ctx context.Context) ([]models.Site, error)
}

// SitesLoadedMsg is what loadSites sends when the call is done.
type SitesLoadedMsg struct {
	Sites []models.Site
	Err   error
}

// loadSites calls the API in the background.
func loadSites(c SitesClient) tea.Cmd {
	return func() tea.Msg {
		sites, err := c.Sites(context.Background())
		return SitesLoadedMsg{Sites: sites, Err: err}
	}
}
