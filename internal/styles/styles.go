// Package styles holds the colors used to draw the TUI.
package styles

import "github.com/charmbracelet/lipgloss"

// Color palette, based on VS Code's Dark Modern theme.
const (
	ColorForeground lipgloss.Color = "#CCCCCC" // normal text
	ColorBlue       lipgloss.Color = "#0078D4" // accent: borders, focus
	ColorWhite      lipgloss.Color = "#FFFFFF" // text on blue
	ColorGray       lipgloss.Color = "#9D9D9D" // secondary text
	ColorSelection  lipgloss.Color = "#04395E" // selected row
	ColorDark       lipgloss.Color = "#585858" // label background

	ColorOKText   lipgloss.Color = "#73C991"
	ColorWarnText lipgloss.Color = "#CCA700"
	ColorBadText  lipgloss.Color = "#F14C4C"

	// Role names: styles use these instead of the raw colors, so the theme
	// can be changed by editing just these lines.
	Accent   = ColorBlue
	Muted    = ColorGray
	OnAccent = ColorWhite
	Shade    = ColorSelection
	Text     = ColorForeground
	Off      = ColorDark

	// A node's state: free, busy, or down (dead, suspected, absent).
	StatusOK   = ColorOKText
	StatusWarn = ColorWarnText
	StatusBad  = ColorBadText
)
