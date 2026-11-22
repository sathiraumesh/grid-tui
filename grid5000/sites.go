package grid5000

import (
	"context"

	"grid-tui/models"
)

// SitesPath is the API path of the list of sites.
const SitesPath = "/sites"

// site is one item of GET /sites, as the API sends it. Only the fields
// the app uses are decoded.
type site struct {
	UID         string `json:"uid"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

// Sites lists every Grid'5000 site: GET /stable/sites.
func (c *Client) Sites(ctx context.Context) ([]models.Site, error) {
	var col collection[site]
	if err := c.get(ctx, SitesPath, &col); err != nil {
		return nil, err
	}
	sites := make([]models.Site, 0, len(col.Items))
	for _, s := range col.Items {
		sites = append(sites, models.Site{UID: s.UID, Name: s.Name, Description: s.Description})
	}
	return sites, nil
}
