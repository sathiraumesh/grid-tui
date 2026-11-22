// Package app wires the pieces together and runs the Bubble Tea program.
package app

import (
	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/internal/controllers"
	"grid-tui/internal/grid5000"
)

// App holds the controller Bubble Tea runs.
type App struct {
	controller controllers.Controller
}

// New creates the App: a controller that loads the sites from the
// Grid'5000 API (credentials from G5K_USER and G5K_PASSWORD, see
// grid5000.NewClient).
func New() *App {
	return &App{controller: controllers.New(grid5000.NewClient())}
}

// Run starts the TUI full-screen and blocks until the user quits.
func (a *App) Run() error {
	_, err := tea.NewProgram(a.controller, tea.WithAltScreen()).Run()
	return err
}
