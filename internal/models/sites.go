package models

// Site is one Grid'5000 site, as GET /sites lists it.
type Site struct {
	UID         string // e.g. "nancy": used in every API path
	Name        string // e.g. "Nancy"
	Description string // e.g. "Grid5000 Nancy site"
}

// Sites is the list of Grid'5000 sites.
type Sites struct {
	Items []Site
}

var _ Model = Sites{} // Sites implements Model

// NewSites makes the model of a list of sites.
func NewSites(items []Site) Sites {
	return Sites{Items: items}
}

// Len is how many sites there are.
func (s Sites) Len() int { return len(s.Items) }
