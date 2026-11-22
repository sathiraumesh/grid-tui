// Package app wires the pieces together and runs the Bubble Tea program.
package app

import (
	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/internal/controllers"
	"grid-tui/internal/models"
)

// App holds the controller Bubble Tea runs.
type App struct {
	controller controllers.Controller
}

// New creates the App with its starting state: the list of sites, empty
// until the Grid'5000 client loads them.
func New() *App {
	return &App{controller: controllers.New(models.NewSites(nil))}
}

// Run starts the TUI full-screen and blocks until the user quits.
func (a *App) Run() error {
	_, err := tea.NewProgram(a.controller, tea.WithAltScreen()).Run()
	return err
}
