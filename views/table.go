package views

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// columnGap is the number of spaces between two columns.
const columnGap = 3

// table lines up rows under columns: every column is as wide as its
// widest cell, title included. The first line is the titles, in Header.
//
//	SITE     NAME     DESCRIPTION
//	nancy    Nancy    Grid5000 Nancy site
func table(columns []string, rows [][]string) []string {
	widths := make([]int, len(columns))
	for i, c := range columns {
		widths[i] = lipgloss.Width(c)
	}
	for _, r := range rows {
		for i, cell := range r {
			if i < len(widths) {
				widths[i] = max(widths[i], lipgloss.Width(cell))
			}
		}
	}

	line := func(cells []string) string {
		var b strings.Builder
		for i, cell := range cells {
			b.WriteString(cell)
			if i < len(cells)-1 && i < len(widths) {
				b.WriteString(strings.Repeat(" ", widths[i]-lipgloss.Width(cell)+columnGap))
			}
		}
		return strings.TrimRight(b.String(), " ")
	}

	out := make([]string, 0, len(rows)+1)
	out = append(out, Header.Render(line(columns)))
	for _, r := range rows {
		out = append(out, line(r))
	}
	return out
}
