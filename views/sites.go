package views

import (
	"strconv"

	"grid-tui/models"
)

// SitesView draws the list of Grid'5000 sites, the selected one highlighted:
//
//	┌─   sites: 2   ─────────────────────────────────┐
//	│                                                │
//	│ SITE     NAME     DESCRIPTION                  │
//	│ nancy    Nancy    Grid5000 Nancy site          │  ◀ selected
//	│ rennes   Rennes   Grid5000 Rennes site         │
//	└─ $ curl https://api.grid5000.fr/stable/sites ──┘
type SitesView struct {
	Sites models.Sites
}

var _ Selectable = SitesView{} // SitesView implements Selectable (and View)

var siteColumns = []string{"SITE", "NAME", "DESCRIPTION"}

func (v SitesView) Labels() []string {
	return []string{"sites: " + strconv.Itoa(v.Sites.Len())}
}

func (v SitesView) Command() string {
	return "curl https://api.grid5000.fr/stable/sites"
}

func (v SitesView) Help() string {
	return "↑↓ move • ←→ scroll • enter clusters • / search • r reload • q quit"
}

// Lines is the sites as a table, or none while there are no sites (the
// panel then says there is nothing to show).
func (v SitesView) Lines() []string {
	if v.Sites.Len() == 0 {
		return nil
	}
	rows := make([][]string, 0, v.Sites.Len())
	for _, s := range v.Sites.Items {
		rows = append(rows, []string{s.UID, s.Name, s.Description})
	}
	return table(siteColumns, rows)
}

// Pinned keeps the column titles on screen.
func (v SitesView) Pinned() int { return 1 }

// Selected is the selected site's line: under the header row.
func (v SitesView) Selected() int {
	if v.Sites.Len() == 0 {
		return -1
	}
	return v.Sites.Cursor + 1
}
