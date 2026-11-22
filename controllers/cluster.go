package controllers

import (
	"context"
	"errors"
	"sync"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// One cluster in detail: its hardware, and its nodes with their
// reservations, loaded when enter opens the cluster and with r; esc goes
// back to the clusters.
//
//	enter / r ──▶ loadDetail ──runs, together──▶ client.ClusterStatus
//	                                             client.ClusterHardware ──▶ DetailLoadedMsg ──▶ onDetailLoaded

// DetailLoadedMsg is what loadDetail sends when both calls are done.
type DetailLoadedMsg struct {
	Site, Cluster string // what they were loaded for
	Nodes         []models.NodeStatus
	Hardware      models.Hardware
	At            time.Time // when the calls finished: what "now" means
	// Err is the calls' errors joined; what loaded without error is kept.
	NodesErr, HardwareErr error
}

// Err is both calls' errors together, or nil.
func (m DetailLoadedMsg) Err() error { return errors.Join(m.NodesErr, m.HardwareErr) }

// loadDetail calls the API twice, at the same time, in the background.
func loadDetail(c Client, site, cluster string) tea.Cmd {
	return func() tea.Msg {
		ctx := context.Background()
		msg := DetailLoadedMsg{Site: site, Cluster: cluster}
		var wg sync.WaitGroup
		wg.Add(2)
		go func() {
			defer wg.Done()
			msg.Nodes, msg.NodesErr = c.ClusterStatus(ctx, site, cluster)
		}()
		go func() {
			defer wg.Done()
			msg.Hardware, msg.HardwareErr = c.ClusterHardware(ctx, site, cluster)
		}()
		wg.Wait()
		msg.At = time.Now()
		return msg
	}
}

// openCluster shows the detail of the selected cluster and starts loading
// it.
func (c Controller) openCluster() (tea.Model, tea.Cmd) {
	if _, onClusters := c.model.(models.Clusters); !onClusters || c.client == nil || c.loading {
		return c, nil
	}
	cl, ok := c.clusters.Selected()
	if !ok {
		return c, nil
	}
	c.model = models.NewClusterDetail(c.clusters.Site, cl)
	c.loading, c.err = true, nil
	return c, loadDetail(c.client, c.clusters.Site, cl.UID)
}

// onDetailLoaded stores the nodes and the hardware, if they are for the
// cluster on screen: after esc, or for another cluster, they arrive too
// late and are dropped. A part that failed keeps what was there before.
func (c Controller) onDetailLoaded(msg DetailLoadedMsg) Controller {
	d, ok := c.model.(models.ClusterDetail)
	if !ok || d.Site != msg.Site || d.Cluster.UID != msg.Cluster {
		return c
	}
	if msg.NodesErr == nil {
		d = d.WithNodes(msg.Nodes, msg.At)
	}
	if msg.HardwareErr == nil {
		d = d.WithHardware(msg.Hardware)
	}
	c.model = d
	c.loading, c.err = false, msg.Err()
	return c
}
