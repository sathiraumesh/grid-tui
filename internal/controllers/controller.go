// Package controllers turns messages (key presses, resizes, data arriving)
// into changes of state. Controller is the tea.Model Bubble Tea runs:
// Update changes the state, View hands it to views.Render.
package controllers

import (
	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/internal/models"
	"grid-tui/internal/views"
)

// Controller holds the model the panel shows, the terminal size and
// whether a load is on its way.
type Controller struct {
	client SitesClient // nil: nothing is loaded

	model         models.Model
	width, height int   // 0 until the first resize
	loading       bool  // a load is on its way
	err           error // the last load's error; the old data is kept
}

// New makes a controller that loads the sites with client.
func New(client SitesClient) Controller {
	return Controller{client: client, model: models.NewSites(nil), loading: client != nil}
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
		c.loading, c.err = false, msg.Err
		if msg.Err == nil {
			c.model = models.NewSites(msg.Sites)
		}

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
	case keyReload:
		if c.client == nil || c.loading {
			return c, nil // nothing to load with, or already loading
		}
		c.loading, c.err = true, nil
		return c, loadSites(c.client)
	}
	return c, nil
}
