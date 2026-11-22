package models

import (
	"slices"
	"time"
)

// ClusterDetail is one cluster in detail: its hardware, its nodes and
// their reservations, and the selected node.
type ClusterDetail struct {
	Site     string
	Cluster  Cluster
	Hardware Hardware     // zero while loading
	Nodes    []NodeStatus // sorted by name; nil while loading
	At       time.Time    // when the nodes were loaded: what "now" means

	Cursor int // index of the selected node
}

var _ Model = ClusterDetail{} // ClusterDetail implements Model

// NewClusterDetail makes the detail of cluster c of site, with no nodes yet.
func NewClusterDetail(site string, c Cluster) ClusterDetail {
	return ClusterDetail{Site: site, Cluster: c}
}

// WithNodes stores the nodes loaded at at, sorted by name, keeping the
// selection inside the list.
func (d ClusterDetail) WithNodes(nodes []NodeStatus, at time.Time) ClusterDetail {
	d.Nodes = slices.Clone(nodes)
	sortNodes(d.Nodes)
	d.At = at
	return d.Move(0)
}

// WithHardware stores the hardware of the cluster.
func (d ClusterDetail) WithHardware(h Hardware) ClusterDetail {
	d.Hardware = h
	return d
}

// Len is how many nodes there are.
func (d ClusterDetail) Len() int { return len(d.Nodes) }

// Move moves the selected node by step (negative is up), within the list.
func (d ClusterDetail) Move(step int) ClusterDetail {
	d.Cursor = moveCursor(d.Cursor, step, len(d.Nodes))
	return d
}

// Selected is the selected node, or false if there are none.
func (d ClusterDetail) Selected() (NodeStatus, bool) {
	if d.Cursor < 0 || d.Cursor >= len(d.Nodes) {
		return NodeStatus{}, false
	}
	return d.Nodes[d.Cursor], true
}

// Counts are how many nodes are in each state at At.
type Counts struct {
	Alive, Free, Busy, Down int
}

// CountsNow counts the nodes by what they do at At. A node with only a
// besteffort job counts as free: a regular job can have it.
func (d ClusterDetail) CountsNow() Counts {
	var c Counts
	for _, n := range d.Nodes {
		switch n.SlotAt(d.At, d.At.Add(time.Second)) {
		case SlotDown:
			c.Down++
			continue
		case SlotBusy:
			c.Busy++
		default:
			c.Free++
		}
		c.Alive++
	}
	return c
}
