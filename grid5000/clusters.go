package grid5000

import (
	"context"
	"errors"
	"net/url"

	"grid-tui/models"
)

// cluster is one item of GET /sites/{site}/clusters, as the API sends it.
// Only the fields the app uses are decoded.
type cluster struct {
	UID     string   `json:"uid"`
	Model   string   `json:"model"`
	Queues  []string `json:"queues"`
	Metrics []struct {
		Name        string `json:"name"`
		Description string `json:"description"`
		Period      number `json:"period"` // milliseconds
		Optional    bool   `json:"optional"`
	} `json:"metrics"`
}

// ClustersPath is the API path of the clusters of site.
func ClustersPath(site string) string {
	return SitesPath + "/" + url.PathEscape(site) + "/clusters"
}

// Clusters lists the clusters of a site: GET /stable/sites/{site}/clusters.
func (c *Client) Clusters(ctx context.Context, site string) ([]models.Cluster, error) {
	if site == "" {
		return nil, errors.New("clusters: no site given")
	}
	var col collection[cluster]
	if err := c.get(ctx, ClustersPath(site), &col); err != nil {
		return nil, err
	}
	clusters := make([]models.Cluster, 0, len(col.Items))
	for _, cl := range col.Items {
		mc := models.Cluster{UID: cl.UID, Model: cl.Model, Queues: cl.Queues}
		for _, m := range cl.Metrics {
			mc.Metrics = append(mc.Metrics, models.Metric{Name: m.Name, Description: m.Description, PeriodMs: int(m.Period), Optional: m.Optional})
		}
		clusters = append(clusters, mc)
	}
	return clusters, nil
}
