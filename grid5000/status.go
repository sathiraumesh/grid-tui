package grid5000

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/url"
	"strconv"
	"strings"
	"time"

	"grid-tui/models"
)

// The status of a cluster: every node's OAR state and its current and
// future jobs. The answer looks like this (abridged):
//
//	{"nodes": {
//	  "gros-12.nancy.grid5000.fr": {
//	    "hard": "alive", "soft": "busy",
//	    "reservations": [{"uid": 4521, "user": "bob", "queue": "default",
//	      "state": "Running", "walltime": 7200,
//	      "started_at": 1795000000, "scheduled_at": 1795000000}]}}}
//
// Times are UNIX seconds, walltime is seconds. A job that hasn't started
// has no started_at; its scheduled_at is when OAR plans to start it.

// StatusPath is the API path of the status of a cluster.
func StatusPath(site, cluster string) string {
	return ClustersPath(site) + "/" + url.PathEscape(cluster) + "/status"
}

type status struct {
	Nodes map[string]nodeStatus `json:"nodes"`
}

type nodeStatus struct {
	Hard         string        `json:"hard"`
	Soft         string        `json:"soft"`
	Reservations []reservation `json:"reservations"`
}

type reservation struct {
	UID         number `json:"uid"`
	User        string `json:"user"`
	Queue       string `json:"queue"`
	State       string `json:"state"`
	Walltime    number `json:"walltime"`
	StartedAt   number `json:"started_at"`
	ScheduledAt number `json:"scheduled_at"`
}

// ClusterStatus lists the nodes of a cluster with their jobs:
// GET /stable/sites/{site}/clusters/{cluster}/status.
//
// Jobs with no start time yet (not scheduled) are left out.
func (c *Client) ClusterStatus(ctx context.Context, site, cluster string) ([]models.NodeStatus, error) {
	if site == "" || cluster == "" {
		return nil, errors.New("cluster status: site and cluster are needed")
	}
	var st status
	if err := c.get(ctx, StatusPath(site, cluster), &st); err != nil {
		return nil, err
	}
	nodes := make([]models.NodeStatus, 0, len(st.Nodes))
	for fqdn, ns := range st.Nodes {
		n := models.NodeStatus{
			Name: strings.SplitN(fqdn, ".", 2)[0], // gros-12.nancy.grid5000.fr → gros-12
			Hard: ns.Hard,
			Soft: ns.Soft,
		}
		for _, r := range ns.Reservations {
			start := int64(r.StartedAt)
			if start == 0 {
				start = int64(r.ScheduledAt)
			}
			if start == 0 || r.Walltime <= 0 {
				continue
			}
			n.Reservations = append(n.Reservations, models.Reservation{
				JobID: int64(r.UID), User: r.User, Queue: r.Queue, State: r.State,
				Start: time.Unix(start, 0),
				End:   time.Unix(start+int64(r.Walltime), 0),
			})
		}
		nodes = append(nodes, n)
	}
	return nodes, nil
}

// number reads a JSON number, a number in a string, or null (as 0), so a
// field the API sends in another form doesn't fail the whole answer.
type number int64

func (n *number) UnmarshalJSON(b []byte) error {
	b = bytes.Trim(b, `"`)
	if len(b) == 0 || string(b) == "null" {
		*n = 0
		return nil
	}
	f, err := strconv.ParseFloat(string(b), 64)
	if err != nil {
		return err
	}
	*n = number(f)
	return nil
}

var _ json.Unmarshaler = (*number)(nil)
