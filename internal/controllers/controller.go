// Package controllers turns messages (key presses, resizes, data arriving)
// into changes of state. Controller is the tea.Model Bubble Tea runs:
// Update changes the state, View hands it to views.Render.
package controllers

import (
	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/internal/models"
	"grid-tui/internal/views"
)

// Controller holds the model the panel shows and the terminal size.
type Controller struct {
	model         models.Model
	width, height int // 0 until the first resize
}

// New makes a controller showing m.
func New(m models.Model) Controller {
	return Controller{model: m}
}

// Model returns the model the panel shows.
func (c Controller) Model() models.Model { return c.model }

// Size returns the terminal size.
func (c Controller) Size() (width, height int) { return c.width, c.height }

// Init starts nothing yet.
func (c Controller) Init() tea.Cmd { return nil }

// View draws the current model.
func (c Controller) View() string { return views.Render(views.For(c.model), c.width, c.height) }

// Update handles one message and returns the new controller.
func (c Controller) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		c.width, c.height = msg.Width, msg.Height
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
	}
	return c, nil
}
