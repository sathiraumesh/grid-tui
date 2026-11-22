package models

// Site is one Grid'5000 site, as GET /sites lists it.
type Site struct {
	UID         string // e.g. "nancy": used in every API path
	Name        string // e.g. "Nancy"
	Description string // e.g. "Grid5000 Nancy site"
}

// Sites is the list of Grid'5000 sites and which one is selected.
type Sites struct {
	Items  []Site
	Cursor int // index of the selected site
}

var _ Model = Sites{} // Sites implements Model

// NewSites makes the model of a list of sites, the first one selected.
func NewSites(items []Site) Sites {
	return Sites{Items: items}
}

// Len is how many sites there are.
func (s Sites) Len() int { return len(s.Items) }

// Move moves the selection by step (negative is up), within the list.
func (s Sites) Move(step int) Sites {
	s.Cursor = moveCursor(s.Cursor, step, len(s.Items))
	return s
}

// WithItems replaces the sites (after a reload), keeping the selection
// inside the new list.
func (s Sites) WithItems(items []Site) Sites {
	s.Items = items
	return s.Move(0)
}

// Selected is the selected site, or false if there are none.
func (s Sites) Selected() (Site, bool) {
	if s.Cursor < 0 || s.Cursor >= len(s.Items) {
		return Site{}, false
	}
	return s.Items[s.Cursor], true
}
