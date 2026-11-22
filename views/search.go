package views

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"

	"grid-tui/models"
)

// SearchView draws the search: the form of requirements, then the
// clusters of every site that meet them. The form and the column titles
// stay on screen while the results scroll.
//
//	┌─   search  ───  matches: 2 of 41  ───  loading sites 7/9   ─────────────┐
//	│                                                                          │
//	│ ▸ Has GPU                [x]                                             │  ◀ focused
//	│   Wattmeter              [ ]                                             │
//	│   Site                   ◀ any ▶                                         │
//	│   CPU                    ◀ Intel ▶                                       │
//	│   …                                                                      │
//	│   Min cores / node       [ 32 ]                                          │
//	│                                                                          │
//	│ SITE   CLUSTER   NODES   CPU                       CORES   MEMORY  GPU … │
//	│ lyon   gemini    2       1 × Intel Xeon E5-2698   40      512 GiB 2 × …  │
//	└─ $ curl …/sites/{site}/clusters and …/clusters/{cluster}/nodes ─────────┘
type SearchView struct {
	Search models.Search
}

var _ Selectable = SearchView{} // SearchView implements Selectable (and View)
var _ Pinned = SearchView{}     // and keeps the form on screen

var searchColumns = append([]string{"SITE"}, clusterColumns...)

func (v SearchView) Labels() []string {
	s := v.Search
	labels := []string{"search", fmt.Sprintf("matches: %d of %d", s.Len(), len(s.Entries))}
	if s.Loading() {
		labels = append(labels, fmt.Sprintf("loading sites %d/%d", s.SitesDone, s.SitesTotal))
	}
	return labels
}

func (v SearchView) Command() string {
	return "curl https://api.grid5000.fr/stable/sites/{site}/clusters and …/clusters/{cluster}/nodes, for every site"
}

func (v SearchView) Help() string {
	i, onField := v.Search.FocusedField()
	if !onField {
		return "↑↓ move • enter details • ←→ scroll • r reload • esc sites • q quit"
	}
	switch models.SearchFields[i].Kind {
	case models.FieldFlag:
		return "↑↓ fields • enter/space tick • esc sites • q quit"
	case models.FieldChoice:
		return "↑↓ fields • enter/←→ choose • esc sites • q quit"
	}
	return "↑↓ fields • type a number • ⌫ delete • esc sites • q quit"
}

// Lines is the form, an empty line, then the results as a table.
func (v SearchView) Lines() []string {
	s := v.Search
	labelW := 0
	for _, f := range models.SearchFields {
		labelW = max(labelW, lipgloss.Width(f.Label))
	}
	focus, onField := s.FocusedField()

	lines := make([]string, 0, len(models.SearchFields)+2+s.Len())
	for i, f := range models.SearchFields {
		mark := "  "
		if onField && i == focus {
			mark = "▸ "
		}
		pad := strings.Repeat(" ", labelW-lipgloss.Width(f.Label)+3)
		lines = append(lines, mark+f.Label+pad+fieldValue(f, s.Value(i)))
	}
	lines = append(lines, "")

	results := s.Results()
	rows := make([][]string, 0, len(results))
	for _, e := range results {
		rows = append(rows, append([]string{e.Site, e.Cluster.UID}, hardwareCells(e.Cluster)...))
	}
	lines = append(lines, table(searchColumns, rows)...)
	if len(rows) == 0 {
		if s.Loading() {
			lines = append(lines, Help.Render("loading the clusters of every site…"))
		} else {
			lines = append(lines, Help.Render("no cluster meets these requirements"))
		}
	}
	return lines
}

// fieldValue is how a field shows its value: [x], ◀ Intel ▶ or [ 32 ].
func fieldValue(f models.SearchField, v string) string {
	switch f.Kind {
	case models.FieldFlag:
		if v == models.Ticked {
			return "[x]"
		}
		return "[ ]"
	case models.FieldChoice:
		if v == "" {
			v = models.Any
		}
		return "◀ " + v + " ▶"
	}
	return "[ " + fmt.Sprintf("%-4s", v) + " ]"
}

// Pinned keeps the form, the empty line and the column titles on screen.
func (v SearchView) Pinned() int { return len(models.SearchFields) + 2 }

// Selected is the focused field's line, or the focused result's.
func (v SearchView) Selected() int {
	s := v.Search
	if i, onField := s.FocusedField(); onField {
		return i
	}
	if _, ok := s.Selected(); !ok {
		return -1
	}
	return v.Pinned() + s.Focus - len(models.SearchFields)
}
