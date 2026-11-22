// Package views draws the screen. Views only read a model and return
// strings: they never change it and never do slow work.
//
// Each kind of model has its view (SitesView for models.Sites, …), and
// For picks it. Every view implements View, so Render draws them all the
// same way: a bordered panel with labels on top and a command below.
package views

import (
	"strings"

	"github.com/charmbracelet/lipgloss"

	"grid-tui/internal/models"
)

// View is what the panel draws for one model.
type View interface {
	// Labels are set into the panel's top border, left to right.
	Labels() []string

	// Command is the API call behind the data, shown on the bottom border.
	Command() string

	// Lines are the panel's rows. None means there is nothing to show yet.
	Lines() []string
}

// For returns the view of m, or nil if m is nil or has no view.
func For(m models.Model) View {
	switch m := m.(type) {
	case models.Sites:
		return SitesView{Sites: m}
	}
	return nil
}

// HelpText is the key-hint line at the bottom of the screen.
const HelpText = "q quit"

// emptyText is shown inside the panel while the view has no lines.
const emptyText = "nothing to show yet"

// Render draws the whole screen for v, exactly width × height cells. v may
// be nil: then the panel is empty.
//
//	margin        panelMarginY rows
//	panel         everything that's left
//	margin        panelMarginY rows
//	help line     1 row
func Render(v View, width, height int) string {
	if width == 0 {
		return "loading..."
	}
	help := lipgloss.NewStyle().MaxWidth(width).Render(Help.Render(HelpText))
	return lipgloss.JoinVertical(lipgloss.Left, panel(v, width, height), help)
}

// ContentHeight is how many rows fit inside the panel: the terminal's
// height minus the help line, the margins, the panel's top and bottom
// border and the empty row under the top border. It is at least 1.
func ContentHeight(height int) int {
	return max(height-1-2*panelMarginY-2-panelPaddingTop, 1)
}

// panel draws the bordered box with the view's lines and border texts.
func panel(v View, width, height int) string {
	panelW := width - 2  // minus the left and right border
	innerW := panelW - 2 // minus the padding
	h := ContentHeight(height)

	var labels, lines []string
	var command string
	if v != nil {
		labels, command, lines = v.Labels(), v.Command(), v.Lines()
	}
	if len(lines) == 0 {
		lines = []string{Help.Render(emptyText)}
	}
	lines = lines[:min(len(lines), h)]
	// A line wider than the panel is cut off: a wrapped one would make the
	// panel taller than the screen.
	content := lipgloss.NewStyle().MaxWidth(innerW).Render(strings.Join(lines, "\n"))

	body := Panel.PaddingTop(panelPaddingTop).
		Width(panelW).
		Height(h + panelPaddingTop).
		Render(content)
	w := lipgloss.Width(body)

	// Top border: the view's labels.
	if len(labels) > 0 {
		drawn := make([]string, len(labels))
		for i, l := range labels {
			drawn[i] = label.Render(l)
		}
		body = withBorderText(body, edgeTop, labelRow(drawn...), "", w)
	}

	// Bottom border: the API call behind the data.
	if command != "" {
		cmd := lipgloss.NewStyle().MaxWidth(max(w-6, 0)).Render("$ " + command) // 6 = "└─ " + " ─┘"
		body = withBorderText(body, edgeBottom, borderLabel(commandStyle, cmd), "", w)
	}

	// Margins are added last: the border texts need the borders to be the
	// panel's first and last lines.
	return lipgloss.NewStyle().MarginTop(panelMarginY).MarginBottom(panelMarginY).Render(body)
}
