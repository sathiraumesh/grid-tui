// Package views draws the screen. Views only read a model and return
// strings: they never change it and never do slow work.
//
// What is shared lives here (View, For, Render); each kind of model has its
// own view in its own file:
//
//	sites.go      SitesView, for models.Sites
//	clusters.go   ClustersView, for models.Clusters
//	cluster.go    ClusterDetailView, for models.ClusterDetail
//
// Every view implements View, so Render draws them all the same way: a
// bordered panel with labels on top, a command below and a help line.
package views

import (
	"strings"

	"github.com/charmbracelet/lipgloss"

	"grid-tui/models"
)

// View is what the panel draws for one model.
type View interface {
	// Labels are set into the panel's top border, left to right.
	Labels() []string

	// Command is the API call behind the data, shown on the bottom border.
	Command() string

	// Lines are the panel's rows. None means there is nothing to show yet.
	Lines() []string

	// Help is the key hints for this view, on the bottom line.
	Help() string
}

// Selectable is a View with a selected line: Render highlights it and
// scrolls to keep it on screen. Selected is an index into Lines, or -1.
type Selectable interface {
	View
	Selected() int
}

// Pinned is a View whose first Pinned() lines (info, column titles) stay
// on screen while the rest scrolls.
type Pinned interface {
	View
	Pinned() int
}

// For returns the view of m, or nil if m is nil or has no view.
func For(m models.Model) View {
	switch m := m.(type) {
	case models.Sites:
		return SitesView{Sites: m}
	case models.Clusters:
		return ClustersView{Clusters: m}
	case models.ClusterDetail:
		return ClusterDetailView{Detail: m}
	}
	return nil
}

// defaultHelp is the help line when there is no view.
const defaultHelp = "q quit"

// emptyText is shown inside the panel while the view has no lines.
const emptyText = "nothing to show yet"

// Status is how the last load went, shown on the bottom line instead of
// the help while there is something to say.
type Status struct {
	Loading bool  // a load is on its way
	Err     error // the last load failed
}

// Render draws the whole screen for v, exactly width × height cells. v may
// be nil: then the panel is empty.
//
//	margin        panelMarginY rows
//	panel         everything that's left
//	margin        panelMarginY rows
//	bottom line   1 row: the error, "loading…", or the help
func Render(v View, status Status, width, height int) string {
	if width == 0 {
		return "loading..."
	}
	help := defaultHelp
	if v != nil {
		help = v.Help()
	}
	// MaxWidth cuts the line at the terminal edge: a wrapped line would be
	// an extra row and push the panel off the top.
	bottom := lipgloss.NewStyle().MaxWidth(width).Render(bottomLine(status, help))
	return lipgloss.JoinVertical(lipgloss.Left, panel(v, width, height), bottom)
}

// bottomLine is the error (red, then the help), "loading…", or the help.
func bottomLine(s Status, help string) string {
	switch {
	case s.Err != nil:
		// Joined errors are one per line: keep them on the one bottom line.
		msg := strings.ReplaceAll(s.Err.Error(), "\n", "; ")
		return ErrorText.Render("error: "+msg) + Help.Render(" • r retry • "+help)
	case s.Loading:
		return Help.Render("loading… • q quit")
	}
	return Help.Render(help)
}

// ContentHeight is how many rows fit inside the panel: the terminal's
// height minus the bottom line, the margins, the panel's top and bottom
// border and the empty row under the top border. It is at least 1.
func ContentHeight(height int) int {
	return max(height-1-2*panelMarginY-2-panelPaddingTop, 1)
}

// window returns the lines that fit in h rows: the first pinned lines,
// then the rest scrolled as little as needed to keep line sel on screen.
// It also returns sel's index in the result (-1 if none).
//
//	lines:  P P a b c d e f      pinned = 2, h = 5, sel = 6 ("e")
//	shown:  P P c d e            sel → 4
func window(lines []string, pinned, sel, h int) ([]string, int) {
	pinned = max(min(pinned, len(lines), h), 0)
	out := append([]string(nil), lines[:pinned]...)
	rest, room := lines[pinned:], h-pinned

	rsel := sel - pinned // sel within rest; negative if none or pinned
	first := 0
	if rsel >= room {
		first = rsel - room + 1
	}
	end := min(first+room, len(rest))
	out = append(out, rest[first:end]...)

	switch {
	case sel >= 0 && sel < pinned:
		return out, sel
	case rsel >= first && rsel < end:
		return out, pinned + rsel - first
	}
	return out, -1
}

// panel draws the bordered box with the view's lines and border texts.
func panel(v View, width, height int) string {
	panelW := width - 2  // minus the left and right border
	innerW := panelW - 2 // minus the padding
	h := ContentHeight(height)

	var labels, lines []string
	var command string
	sel, pinned := -1, 0
	if v != nil {
		labels, command, lines = v.Labels(), v.Command(), v.Lines()
		if s, ok := v.(Selectable); ok {
			sel = s.Selected()
		}
		if p, ok := v.(Pinned); ok {
			pinned = p.Pinned()
		}
	}
	if len(lines) == 0 {
		lines, sel, pinned = []string{Help.Render(emptyText)}, -1, 0
	}
	lines, sel = window(lines, pinned, sel, h)

	// A line wider than the panel is cut off: a wrapped one would make the
	// panel taller than the screen. The selected one is highlighted across
	// the whole width.
	cut := lipgloss.NewStyle().MaxWidth(innerW)
	drawn := make([]string, len(lines))
	for i, l := range lines {
		drawn[i] = cut.Render(l)
		if i == sel {
			drawn[i] = Selected.Width(innerW).Render(drawn[i])
		}
	}

	body := Panel.PaddingTop(panelPaddingTop).
		Width(panelW).
		Height(h + panelPaddingTop).
		Render(strings.Join(drawn, "\n"))
	w := lipgloss.Width(body)

	// Top border: the view's labels.
	if len(labels) > 0 {
		pills := make([]string, len(labels))
		for i, l := range labels {
			pills[i] = label.Render(l)
		}
		body = withBorderText(body, edgeTop, labelRow(pills...), "", w)
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
