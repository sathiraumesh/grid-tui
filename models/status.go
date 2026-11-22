package models

import (
	"sort"
	"strconv"
	"strings"
	"time"
)

// Reservation is an OAR job holding (or scheduled to hold) a node.
type Reservation struct {
	JobID      int64
	User       string
	Queue      string // e.g. "default", "production", "besteffort"
	State      string // e.g. "Running", "Waiting"
	Start, End time.Time
}

// BestEffort jobs are killed by OAR when a regular job needs the node, so
// they don't really keep it busy.
func (r Reservation) BestEffort() bool { return r.Queue == "besteffort" }

// NodeStatus is one node of a cluster: its OAR states and its jobs.
type NodeStatus struct {
	Name         string // short name, e.g. "gros-12"
	Hard         string // alive, absent, suspected, dead
	Soft         string // free, busy, busy_besteffort, unknown
	Reservations []Reservation
}

// Usable is whether the node can take jobs: its hard state is alive.
func (n NodeStatus) Usable() bool { return n.Hard == "alive" }

// Slot is what a node is doing during a period of time.
type Slot int

const (
	SlotFree       Slot = iota // no job
	SlotBusy                   // a regular job
	SlotBestEffort             // only besteffort jobs
	SlotDown                   // not usable (dead, suspected, absent)
)

// SlotAt is what the node does during [from, to): down if it isn't
// usable, busy if a regular job overlaps, besteffort if only besteffort
// jobs do, else free.
func (n NodeStatus) SlotAt(from, to time.Time) Slot {
	if !n.Usable() {
		return SlotDown
	}
	slot := SlotFree
	for _, r := range n.Reservations {
		if r.Start.Before(to) && r.End.After(from) {
			if !r.BestEffort() {
				return SlotBusy
			}
			slot = SlotBestEffort
		}
	}
	return slot
}

// Upcoming is the node's jobs that haven't ended at t, by start time.
func (n NodeStatus) Upcoming(t time.Time) []Reservation {
	var out []Reservation
	for _, r := range n.Reservations {
		if r.End.After(t) {
			out = append(out, r)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Start.Before(out[j].Start) })
	return out
}

// sortNodes orders nodes by name, numbers as numbers: gros-2 before gros-10.
func sortNodes(nodes []NodeStatus) {
	sort.SliceStable(nodes, func(i, j int) bool {
		pi, ni := splitNumber(nodes[i].Name)
		pj, nj := splitNumber(nodes[j].Name)
		if pi != pj {
			return pi < pj
		}
		return ni < nj
	})
}

// splitNumber splits "gros-12" into "gros" and 12.
func splitNumber(name string) (string, int) {
	i := strings.LastIndex(name, "-")
	if i < 0 {
		return name, 0
	}
	n, err := strconv.Atoi(name[i+1:])
	if err != nil {
		return name, 0
	}
	return name[:i], n
}
