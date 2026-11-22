// Package controllers turns messages (key presses, resizes, data arriving)
// into changes of state. Controller is the tea.Model Bubble Tea runs:
// Update changes the state, View hands it to views.Render.
//
// What is shared lives here; each screen has its own file with its
// message, its loader and what its keys do:
//
//	sites.go      the list of sites: load them, enter opens a site
//	clusters.go   the clusters of a site: load them, enter opens a cluster
//	cluster.go    one cluster in detail: its hardware, nodes and their jobs
//
// The screens, and the keys between them:
//
//	Sites ──enter──▶ Clusters of a site ──enter──▶ Cluster detail
//	      ◀──esc───                     ◀──esc───
//
// Calling the API can take seconds, so it never runs in Update: Update
// returns a command, Bubble Tea runs it in the background, and its result
// comes back to Update as a message.
package controllers

import (
	"context"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
	"grid-tui/views"
)

// Client is what loads the data: *grid5000.Client in the app, a fake in
// tests.
type Client interface {
	Sites(ctx context.Context) ([]models.Site, error)
	Clusters(ctx context.Context, site string) ([]models.Cluster, error)
	ClusterStatus(ctx context.Context, site, cluster string) ([]models.NodeStatus, error)
	ClusterHardware(ctx context.Context, site, cluster string) (models.Hardware, error)
}

// Controller holds what the panel shows, the terminal size and whether a
// load is on its way.
type Controller struct {
	client Client // nil: nothing is loaded

	// The lists are kept while a deeper screen is shown, so esc returns to
	// the same row.
	sites    models.Sites
	clusters models.Clusters
	model    models.Model // what the panel shows now: sites, clusters or a cluster

	width, height int   // 0 until the first resize
	loading       bool  // a load for the model shown is on its way
	err           error // the last load's error; the old data is kept
}

// New makes a controller that starts on the list of sites, loaded with
// client.
func New(client Client) Controller {
	sites := models.NewSites(nil)
	return Controller{client: client, sites: sites, model: sites, loading: client != nil}
}

// Model returns the model the panel shows.
func (c Controller) Model() models.Model { return c.model }

// Size returns the terminal size.
func (c Controller) Size() (width, height int) { return c.width, c.height }

// Init starts loading the sites.
func (c Controller) Init() tea.Cmd {
	if c.client == nil {
		return nil
	}
	return loadSites(c.client)
}

// View draws the current model.
func (c Controller) View() string {
	status := views.Status{Loading: c.loading, Err: c.err}
	return views.Render(views.For(c.model), status, c.width, c.height)
}

// Update handles one message and returns the new controller.
func (c Controller) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		c.width, c.height = msg.Width, msg.Height
	case SitesLoadedMsg:
		return c.onSitesLoaded(msg), nil
	case ClustersLoadedMsg:
		return c.onClustersLoaded(msg), nil
	case DetailLoadedMsg:
		return c.onDetailLoaded(msg), nil
	case tea.KeyMsg:
		return c.onKey(msg)
	}
	return c, nil
}

// onKey is what each key does.
func (c Controller) onKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case keyQuit, keyCtrlC:
		return c, tea.Quit
	case keyUp, keyUpAlt:
		return c.move(-1), nil
	case keyDown, keyDownAlt:
		return c.move(1), nil
	case keyOpen:
		return c.open()
	case keyBack, keyBackAlt:
		return c.back(), nil
	case keyReload:
		return c.reload()
	}
	return c, nil
}

// move moves the selection of the list on screen.
func (c Controller) move(step int) Controller {
	switch m := c.model.(type) {
	case models.Sites:
		c.sites = m.Move(step)
		c.model = c.sites
	case models.Clusters:
		c.clusters = m.Move(step)
		c.model = c.clusters
	case models.ClusterDetail:
		c.model = m.Move(step)
	}
	return c
}

// open goes one screen deeper: a site's clusters, or a cluster's detail.
func (c Controller) open() (tea.Model, tea.Cmd) {
	switch c.model.(type) {
	case models.Sites:
		return c.openSite()
	case models.Clusters:
		return c.openCluster()
	}
	return c, nil
}

// back goes one screen up, to the same row as before. A load still on its
// way for the screen left is dropped when it arrives.
func (c Controller) back() Controller {
	switch c.model.(type) {
	case models.ClusterDetail:
		c.model = c.clusters
	case models.Clusters:
		c.model = c.sites
	default:
		return c
	}
	c.loading, c.err = false, nil
	return c
}

// reload loads the data on screen again.
func (c Controller) reload() (tea.Model, tea.Cmd) {
	if c.client == nil || c.loading {
		return c, nil // nothing to load with, or already loading
	}
	c.loading, c.err = true, nil
	switch m := c.model.(type) {
	case models.Clusters:
		return c, loadClusters(c.client, m.Site)
	case models.ClusterDetail:
		return c, loadDetail(c.client, m.Site, m.Cluster.UID)
	default:
		return c, loadSites(c.client)
	}
}
