package views

import (
	"strconv"

	"grid-tui/models"
)

// ClustersView draws the clusters of one site with what their nodes are
// made of, the selected one highlighted. A row's hardware shows "…" while
// it loads and "?" if it failed.
//
//	┌─   site: nancy   ───   clusters: 2   ─────────────────────────────────────────────────────────────┐
//	│                                                                                                    │
//	│ CLUSTER    NODES   CPU                        CORES   MEMORY    GPU   STORAGE    NETWORK  WATTMETER│
//	│ graffiti   13      1 × Intel Xeon Silver 4110 8       128 GiB   …     …          …        no       │
//	│ gros       124     1 × Intel Xeon Gold 5220   18      96 GiB    -     480 GB SSD 25 Gbps  yes      │
//	└─ $ curl https://api.grid5000.fr/stable/sites/nancy/clusters ──────────────────────────────────────┘
type ClustersView struct {
	Clusters models.Clusters
}

var _ Selectable = ClustersView{} // ClustersView implements Selectable (and View)

var clusterColumns = []string{"CLUSTER", "NODES", "CPU", "CORES", "MEMORY", "GPU", "STORAGE", "NETWORK", "WATTMETER"}

func (v ClustersView) Labels() []string {
	return []string{"site: " + v.Clusters.Site, "clusters: " + strconv.Itoa(v.Clusters.Len())}
}

func (v ClustersView) Command() string {
	return "curl https://api.grid5000.fr/stable/sites/" + v.Clusters.Site + "/clusters"
}

func (v ClustersView) Help() string {
	return "↑↓ move • ←→ scroll • enter details • g reservations • esc sites • r reload • q quit"
}

// Lines is the clusters as a table, or none while there are none (or they
// are still loading).
func (v ClustersView) Lines() []string {
	if v.Clusters.Len() == 0 {
		return nil
	}
	rows := make([][]string, 0, v.Clusters.Len())
	for _, c := range v.Clusters.Items {
		rows = append(rows, append([]string{c.UID}, hardwareCells(c)...))
	}
	return table(clusterColumns, rows)
}

// hardwareCells are a cluster's NODES … WATTMETER cells.
func hardwareCells(c models.Cluster) []string {
	watt := "no"
	if c.Wattmeter() {
		watt = "yes"
	}
	var mark string
	switch c.HardwareState {
	case models.HardwareLoading:
		mark = "…"
	case models.HardwareFailed:
		mark = "?"
	default:
		h := c.Hardware
		return []string{
			orDash(count(h.Nodes)),
			orDash(cpuName(h)),
			orDash(count(h.Cores)),
			orDash(bytesIEC(h.MemoryBytes)),
			orDash(gpus(h.GPUs)),
			orDash(disks(h.Disks)),
			orDash(nics(h.NICs)),
			watt,
		}
	}
	return []string{mark, mark, mark, mark, mark, mark, mark, watt}
}

// cpuName is e.g. "2 × Intel Xeon Gold 5220".
func cpuName(h models.Hardware) string {
	if h.CPU == "" || h.Sockets <= 0 {
		return h.CPU
	}
	return strconv.Itoa(h.Sockets) + " × " + h.CPU
}

// count is n as text, or "" for 0.
func count(n int) string {
	if n <= 0 {
		return ""
	}
	return strconv.Itoa(n)
}

// Pinned keeps the column titles on screen.
func (v ClustersView) Pinned() int { return 1 }

// Selected is the selected cluster's line: under the header row.
func (v ClustersView) Selected() int {
	if v.Clusters.Len() == 0 {
		return -1
	}
	return v.Clusters.Cursor + 1
}
