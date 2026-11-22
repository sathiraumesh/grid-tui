package views

import (
	"strconv"

	"grid-tui/internal/models"
)

// SitesView draws the list of Grid'5000 sites:
//
//	┌─   sites: 2   ─────────────────────────────────┐
//	│                                                │
//	│ SITE     NAME     DESCRIPTION                  │
//	│ nancy    Nancy    Grid5000 Nancy site          │
//	│ rennes   Rennes   Grid5000 Rennes site         │
//	└─ $ curl https://api.grid5000.fr/stable/sites ──┘
type SitesView struct {
	Sites models.Sites
}

var _ View = SitesView{} // SitesView implements View

var siteColumns = []string{"SITE", "NAME", "DESCRIPTION"}

func (v SitesView) Labels() []string {
	return []string{"sites: " + strconv.Itoa(v.Sites.Len())}
}

func (v SitesView) Command() string {
	return "curl https://api.grid5000.fr/stable/sites"
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
