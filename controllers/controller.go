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
//	search.go     the clusters of every site that meet some requirements
//	gantt.go      a cluster's reservations on a time line
//
// The screens, and the keys between them:
//
//	Sites ──enter──▶ Clusters of a site ──enter──▶ Cluster detail ──enter──▶ Reservations
//	      ◀──esc───          │          ◀──esc───        ▲        ◀──esc───      ▲
//	  │                      └──────────g─────────────────┼────────────────────────┘ esc back to the clusters
//	  │                                                   │ enter on a result,
//	  └──/──▶ Search ─────────────────────────────────────┘ esc back to the search
//	        ◀──esc──
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
	sites     models.Sites
	clusters  models.Clusters
	search    models.Search
	returnTo  models.Model // where esc goes from a cluster's detail: its clusters, or the search
	ganttFrom models.Model // where esc goes from the reservations: the detail, or the clusters
	model     models.Model // what the panel shows now

	width, height int   // 0 until the first resize
	scrollX       int   // columns the panel is scrolled to the right
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
	status := views.Status{Loading: c.loading, Err: c.err, ScrollX: c.scrollX}
	return views.Render(views.For(c.model), status, c.width, c.height)
}

// Update handles one message and returns the new controller.
func (c Controller) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		c.width, c.height = msg.Width, msg.Height
		c = c.scroll(0) // a wider terminal may need less scrolling
	case SitesLoadedMsg:
		return c.onSitesLoaded(msg), nil
	case ClustersLoadedMsg:
		return c.onClustersLoaded(msg)
	case HardwareLoadedMsg:
		return c.onHardwareLoaded(msg), nil
	case SiteIndexedMsg:
		return c.onSiteIndexed(msg), nil
	case DetailLoadedMsg:
		return c.onDetailLoaded(msg), nil
	case tea.KeyMsg:
		return c.onKey(msg)
	}
	return c, nil
}

// onKey is what each key does.
func (c Controller) onKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch c.model.(type) {
	case models.Search:
		return c.onSearchKey(msg) // the form takes digits and space
	case models.Gantt:
		return c.onGanttKey(msg) // ←→ move through time
	}
	switch msg.String() {
	case keyQuit, keyCtrlC:
		return c, tea.Quit
	case keyUp, keyUpAlt:
		return c.move(-1), nil
	case keyDown, keyDownAlt:
		return c.move(1), nil
	case keyLeft, keyLeftAlt:
		return c.scroll(-scrollStep), nil
	case keyRight, keyRightAlt:
		return c.scroll(scrollStep), nil
	case keyOpen:
		return c.open()
	case keySearch:
		if _, onSites := c.model.(models.Sites); onSites {
			return c.openSearch()
		}
	case keyGantt:
		if _, onClusters := c.model.(models.Clusters); onClusters {
			return c.openGantt()
		}
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

// scrollStep is how many columns ← and → scroll.
const scrollStep = 8

// scroll moves the panel sideways by step columns, from the left edge to
// where the widest line's end shows.
func (c Controller) scroll(step int) Controller {
	limit := views.MaxScrollX(views.For(c.model), c.width)
	c.scrollX = max(min(c.scrollX+step, limit), 0)
	return c
}

// open goes one screen deeper: a site's clusters, or a cluster's detail.
func (c Controller) open() (tea.Model, tea.Cmd) {
	before := c.model
	var next tea.Model = c
	var cmd tea.Cmd
	switch c.model.(type) {
	case models.Sites:
		next, cmd = c.openSite()
	case models.Clusters:
		next, cmd = c.openCluster()
	case models.ClusterDetail:
		next, cmd = c.openGantt()
	}
	if n := next.(Controller); n.model != nil && !sameScreen(before, n.model) {
		n.scrollX = 0 // a new screen starts at its left edge
		return n, cmd
	}
	return next, cmd
}

// sameScreen is whether a and b are the same kind of model.
func sameScreen(a, b models.Model) bool {
	switch a.(type) {
	case models.Sites:
		_, ok := b.(models.Sites)
		return ok
	case models.Clusters:
		_, ok := b.(models.Clusters)
		return ok
	case models.ClusterDetail:
		_, ok := b.(models.ClusterDetail)
		return ok
	case models.Search:
		_, ok := b.(models.Search)
		return ok
	case models.Gantt:
		_, ok := b.(models.Gantt)
		return ok
	}
	return false
}

// back goes one screen up, to the same row as before. A load still on its
// way for the screen left is dropped when it arrives.
func (c Controller) back() Controller {
	switch c.model.(type) {
	case models.ClusterDetail:
		c.model = c.clusters
		if c.returnTo != nil {
			c.model = c.returnTo
		}
	case models.Clusters, models.Search:
		c.model = c.sites
	default:
		return c
	}
	c.loading, c.err, c.scrollX = false, nil, 0
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
	case models.Gantt:
		return c, loadDetail(c.client, m.Detail.Site, m.Detail.Cluster.UID)
	default:
		return c, loadSites(c.client)
	}
}
