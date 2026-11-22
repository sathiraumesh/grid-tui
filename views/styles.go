package views

import (
	"github.com/charmbracelet/lipgloss"

	"grid-tui/styles"
)

// Lip Gloss styles of each part of the screen. Colors come from the
// palette in the styles package, by role name.
var (
	// Panel draws the main box.
	Panel = lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(styles.Accent).
		Padding(0, 1)

	// Header is the column titles of a table.
	Header = lipgloss.NewStyle().Foreground(styles.Muted).Bold(true)

	// Help is the key-hint line, and gray text in the panel and borders.
	Help = lipgloss.NewStyle().Foreground(styles.Muted)

	// ErrorText is a failed load on the bottom line.
	ErrorText = lipgloss.NewStyle().Foreground(styles.StatusBad).Bold(true)

	// label is a fixed label in the top border, e.g. "site: nancy".
	label = lipgloss.NewStyle().Padding(0, 2).Foreground(styles.OnAccent).Background(styles.Off)

	// commandStyle draws the command on the bottom border.
	commandStyle = lipgloss.NewStyle().Foreground(styles.Text)

	// borderLine draws border pieces in the panel's border colour.
	borderLine = lipgloss.NewStyle().Foreground(styles.Accent)
)

// Layout, in terminal cells.
const (
	panelMarginY    = 1 // empty rows above and below the panel
	panelPaddingTop = 1 // empty rows between the top border and the content
	labelGap        = 3 // border pieces between two labels
)
