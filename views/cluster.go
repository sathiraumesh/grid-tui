package views

import (
	"fmt"
	"strconv"
	"strings"
	"time"

	"grid-tui/models"
)

// ClusterDetailView draws one cluster in detail: its hardware, how many of
// its nodes are free, and every node with its job now or next. The info
// and the column titles stay on screen while the nodes scroll.
//
//	┌─   site: nancy  ───  cluster: gros  ───  nodes: 3   ────────────────────┐
//	│                                                                          │
//	│ MODEL     Dell PowerEdge R640                                            │
//	│ QUEUES    default, admin                                                 │
//	│ CPU       1 × Intel Xeon Gold 5220 · 18 cores · 36 threads · 2.2 GHz     │
//	│ MEMORY    96 GiB                                                         │
//	│ STORAGE   480 GB SSD SATA · 960 GB SSD SATA                              │
//	│ NETWORK   25 Gbps Ethernet                                               │
//	│ GPU       -                                                              │
//	│ WATTMETER yes · wattmetre_power_watt every 20 ms                         │
//	│ METRICS   2: wattmetre_power_watt, bmc_node_power_watt                   │
//	│ NODES     3 · alive 2 · free 1 · busy 1 · down 1                         │
//	│                                                                          │
//	│ NODE      STATE          NOW    JOB                                      │
//	│ gros-1    alive/free     free   next #4600 eve 18:00→19:00 (1h)          │  ◀ selected
//	│ gros-2    alive/busy     busy   #4521 bob 13:30→16:30 (3h) Running       │
//	│ gros-10   dead/unknown   down                                            │
//	└─ $ curl https://api.grid5000.fr/stable/sites/nancy/clusters/gros/status ─┘
type ClusterDetailView struct {
	Detail models.ClusterDetail
}

var _ Selectable = ClusterDetailView{} // ClusterDetailView implements Selectable (and View)
var _ Pinned = ClusterDetailView{}     // and keeps its info on screen

var nodeColumns = []string{"NODE", "STATE", "NOW", "JOB"}

func (v ClusterDetailView) Labels() []string {
	return []string{
		"site: " + v.Detail.Site,
		"cluster: " + v.Detail.Cluster.UID,
		"nodes: " + strconv.Itoa(v.Detail.Len()),
	}
}

func (v ClusterDetailView) Command() string {
	return "curl https://api.grid5000.fr/stable/sites/" + v.Detail.Site +
		"/clusters/" + v.Detail.Cluster.UID + "/status"
}

func (v ClusterDetailView) Help() string {
	return "↑↓ move • ←→ scroll • enter reservations • esc back • r reload • q quit"
}

// Lines is the cluster's info, then its nodes as a table. While the nodes
// are loading only the info is shown.
func (v ClusterDetailView) Lines() []string {
	d := v.Detail
	lines := v.info()
	if d.Len() == 0 {
		return lines
	}

	rows := make([][]string, 0, d.Len())
	for _, n := range d.Nodes {
		rows = append(rows, []string{n.Name, n.Hard + "/" + n.Soft, slotName(n.SlotAt(d.At, d.At.Add(time.Second))), job(n, d.At)})
	}
	return append(lines, table(nodeColumns, rows)...)
}

// info is the cluster's description and node counts, then an empty line.
func (v ClusterDetailView) info() []string {
	d, h := v.Detail, v.Detail.Hardware
	hw := func(s string) string { // a hardware line: "loading" until it is there
		if h.IsZero() {
			return "loading"
		}
		return orDash(s)
	}
	nodes := "loading"
	if !d.At.IsZero() {
		c := d.CountsNow()
		nodes = fmt.Sprintf("%d · alive %d · free %d · busy %d · down %d", d.Len(), c.Alive, c.Free, c.Busy, c.Down)
	}
	info := table([]string{"", ""}, [][]string{
		{"MODEL", orDash(d.Cluster.Model)},
		{"QUEUES", orDash(strings.Join(d.Cluster.Queues, ", "))},
		{"CPU", hw(cpu(h))},
		{"MEMORY", hw(bytesIEC(h.MemoryBytes))},
		{"STORAGE", hw(disks(h.Disks))},
		{"NETWORK", hw(nics(h.NICs))},
		{"GPU", hw(gpus(h.GPUs))},
		{"WATTMETER", wattmeter(d.Cluster)},
		{"METRICS", metrics(d.Cluster.Metrics)},
		{"NODES", nodes},
	})[1:] // no titles: just the aligned rows
	return append(info, "")
}

// Pinned keeps the info and the column titles on screen.
func (v ClusterDetailView) Pinned() int { return len(v.info()) + 1 }

// Selected is the selected node's line: under the info and the titles.
func (v ClusterDetailView) Selected() int {
	if v.Detail.Len() == 0 {
		return -1
	}
	return len(v.info()) + 1 + v.Detail.Cursor
}

// wattmeter is "yes · wattmetre_power_watt every 20 ms" or "no".
func wattmeter(c models.Cluster) string {
	for _, m := range c.Metrics {
		if strings.HasPrefix(m.Name, "wattmetre") {
			text := "yes · " + m.Name
			if m.PeriodMs > 0 {
				text += fmt.Sprintf(" every %d ms", m.PeriodMs)
			}
			return text
		}
	}
	return "no"
}

// metrics is e.g. "3: bmc_node_power_watt, prom_node_load1, wattmetre_power_watt".
func metrics(ms []models.Metric) string {
	if len(ms) == 0 {
		return "-"
	}
	names := make([]string, len(ms))
	for i, m := range ms {
		names[i] = m.Name
	}
	return strconv.Itoa(len(ms)) + ": " + strings.Join(names, ", ")
}

// cpu is e.g. "2 × Intel Xeon Gold 5220 · 36 cores · 72 threads · 2.2 GHz".
func cpu(h models.Hardware) string {
	var parts []string
	if h.CPU != "" {
		name := h.CPU
		if h.Sockets > 0 {
			name = fmt.Sprintf("%d × %s", h.Sockets, h.CPU)
		}
		parts = append(parts, name)
	}
	if h.Cores > 0 {
		parts = append(parts, fmt.Sprintf("%d cores", h.Cores))
	}
	if h.Threads > 0 {
		parts = append(parts, fmt.Sprintf("%d threads", h.Threads))
	}
	if h.ClockGHz > 0 {
		parts = append(parts, strconv.FormatFloat(h.ClockGHz, 'f', -1, 64)+" GHz")
	}
	return strings.Join(parts, " · ")
}

// disks is e.g. "480 GB SSD SATA · 960 GB SSD SATA".
func disks(ds []models.Disk) string {
	parts := make([]string, 0, len(ds))
	for _, d := range ds {
		parts = append(parts, strings.Join(nonEmpty(bytesSI(d.Bytes), d.Kind, d.Interface), " "))
	}
	return strings.Join(parts, " · ")
}

// nics is e.g. "25 Gbps Ethernet · 100 Gbps InfiniBand".
func nics(ns []models.NIC) string {
	parts := make([]string, 0, len(ns))
	for _, n := range ns {
		parts = append(parts, strings.Join(nonEmpty(rate(n.RateBps), n.Interface), " "))
	}
	return strings.Join(parts, " · ")
}

// gpus is e.g. "4 × Nvidia A100 40 GiB": the same cards counted together.
func gpus(gs []models.GPU) string {
	var names []string
	count := map[string]int{}
	for _, g := range gs {
		name := strings.Join(nonEmpty(g.Vendor, g.Model, bytesIEC(g.MemoryBytes)), " ")
		if count[name] == 0 {
			names = append(names, name)
		}
		count[name]++
	}
	parts := make([]string, 0, len(names))
	for _, n := range names {
		if count[n] > 1 {
			n = fmt.Sprintf("%d × %s", count[n], n)
		}
		parts = append(parts, n)
	}
	return strings.Join(parts, " · ")
}

// bytesIEC is a memory size in powers of 1024: "96 GiB", "512 MiB".
func bytesIEC(b int64) string {
	return scaled(float64(b), 1024, []string{"B", "KiB", "MiB", "GiB", "TiB"})
}

// bytesSI is a disk size in powers of 1000, as disks are sold: "480 GB".
func bytesSI(b int64) string {
	return scaled(float64(b), 1000, []string{"B", "kB", "MB", "GB", "TB"})
}

// rate is a network speed: "25 Gbps".
func rate(bps int64) string {
	return scaled(float64(bps), 1000, []string{"bps", "kbps", "Mbps", "Gbps", "Tbps"})
}

// scaled writes v in the largest unit it reaches, with at most one decimal
// ("1.5 TB", "96 GiB"); "" for 0.
func scaled(v, step float64, units []string) string {
	if v <= 0 {
		return ""
	}
	i := 0
	for v >= step && i < len(units)-1 {
		v /= step
		i++
	}
	return strconv.FormatFloat(float64(int64(v*10+0.5))/10, 'f', -1, 64) + " " + units[i]
}

// nonEmpty is the given strings without the empty ones.
func nonEmpty(ss ...string) []string {
	out := ss[:0:0]
	for _, s := range ss {
		if s != "" {
			out = append(out, s)
		}
	}
	return out
}

// slotName is what a node does now, in one word.
func slotName(s models.Slot) string {
	switch s {
	case models.SlotBusy:
		return "busy"
	case models.SlotBestEffort:
		return "besteffort"
	case models.SlotDown:
		return "down"
	}
	return "free"
}

// job is the node's job now, or else its next one, e.g.
// "#4521 bob 13:30→16:30 (3h) Running" or "next #4600 eve 18:00→19:00 (1h)".
func job(n models.NodeStatus, now time.Time) string {
	up := n.Upcoming(now)
	if len(up) == 0 {
		return ""
	}
	r := up[0]
	text := fmt.Sprintf("#%d %s %s→%s (%s)", r.JobID, r.User, clock(r.Start, now), clock(r.End, now), duration(r.End.Sub(r.Start)))
	if r.BestEffort() {
		text += " besteffort"
	}
	if r.Start.After(now) {
		return "next " + text
	}
	return text + " " + r.State
}

// clock is t as "15:04", with the day when it isn't now's day: "Mon 23 09:00".
func clock(t, now time.Time) string {
	if y, m, d := t.Date(); y == now.Year() && m == now.Month() && d == now.Day() {
		return t.Format("15:04")
	}
	return t.Format("Mon 02 15:04")
}

// duration is d as "3h", "1h30m" or "45m".
func duration(d time.Duration) string {
	d = d.Round(time.Minute)
	h, m := int(d.Hours()), int(d.Minutes())%60
	switch {
	case h > 0 && m > 0:
		return fmt.Sprintf("%dh%dm", h, m)
	case h > 0:
		return fmt.Sprintf("%dh", h)
	}
	return fmt.Sprintf("%dm", m)
}

func orDash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}
