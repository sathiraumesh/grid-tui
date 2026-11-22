package views

import (
	"fmt"
	"slices"
	"strings"
	"testing"
	"time"

	"grid-tui/models"
)

var now = time.Date(2026, 11, 22, 14, 30, 0, 0, time.Local)

func at(h float64) time.Time { return now.Add(time.Duration(h * float64(time.Hour))) }

// sampleDetail is a made-up cluster for tests only: gros-1 free with a job
// later, gros-2 running a job, gros-10 dead.
func sampleDetail() models.ClusterDetail {
	gros := models.Cluster{UID: "gros", Model: "Dell PowerEdge R640", Queues: []string{"default", "admin"},
		Metrics: []models.Metric{{Name: "wattmetre_power_watt", PeriodMs: 20}, {Name: "bmc_node_power_watt", PeriodMs: 5000}}}
	hw := models.Hardware{
		CPU: "Intel Xeon Gold 5220", Sockets: 1, Cores: 18, Threads: 36, ClockGHz: 2.2,
		MemoryBytes: 96 << 30,
		Disks:       []models.Disk{{Kind: "SSD", Interface: "SATA", Bytes: 480103981056}, {Kind: "SSD", Interface: "SATA", Bytes: 960197124096}},
		NICs:        []models.NIC{{Interface: "Ethernet", RateBps: 25_000_000_000}},
	}
	return models.NewClusterDetail("nancy", gros).WithHardware(hw).WithNodes([]models.NodeStatus{
		{Name: "gros-10", Hard: "dead", Soft: "unknown"},
		{Name: "gros-2", Hard: "alive", Soft: "busy", Reservations: []models.Reservation{
			{JobID: 4521, User: "bob", Queue: "default", State: "Running", Start: at(-1), End: at(2)},
		}},
		{Name: "gros-1", Hard: "alive", Soft: "free", Reservations: []models.Reservation{
			{JobID: 4600, User: "eve", Queue: "default", State: "Waiting", Start: at(3.5), End: at(4.5)},
		}},
	}, now)
}

// manyNodes is a cluster of n free nodes, to test scrolling.
func manyNodes(n int) models.ClusterDetail {
	nodes := make([]models.NodeStatus, n)
	for i := range nodes {
		nodes[i] = models.NodeStatus{Name: fmt.Sprintf("big-%d", i+1), Hard: "alive", Soft: "free"}
	}
	return models.NewClusterDetail("nancy", models.Cluster{UID: "big"}).WithNodes(nodes, now)
}

func TestClusterDetailViewLines(t *testing.T) {
	v := ClusterDetailView{Detail: sampleDetail()}
	want := []string{
		"MODEL       Dell PowerEdge R640",
		"QUEUES      default, admin",
		"CPU         1 × Intel Xeon Gold 5220 · 18 cores · 36 threads · 2.2 GHz",
		"MEMORY      96 GiB",
		"STORAGE     480.1 GB SSD SATA · 960.2 GB SSD SATA",
		"NETWORK     25 Gbps Ethernet",
		"GPU         -",
		"WATTMETER   yes · wattmetre_power_watt every 20 ms",
		"METRICS     2: wattmetre_power_watt, bmc_node_power_watt",
		"NODES       3 · alive 2 · free 1 · busy 1 · down 1",
		"",
		"NODE      STATE          NOW    JOB",
		"gros-1    alive/free     free   next #4600 eve 18:00→19:00 (1h)",
		"gros-2    alive/busy     busy   #4521 bob 13:30→16:30 (3h) Running",
		"gros-10   dead/unknown   down",
	}
	if got := v.Lines(); !slices.Equal(got, want) {
		t.Errorf("Lines =\n%s\nwant\n%s", strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
	if got := v.Labels(); !slices.Equal(got, []string{"site: nancy", "cluster: gros", "nodes: 3"}) {
		t.Errorf("Labels = %q", got)
	}
	if got := v.Command(); got != "curl https://api.grid5000.fr/stable/sites/nancy/clusters/gros/status" {
		t.Errorf("Command = %q", got)
	}
	if !strings.Contains(v.Help(), "esc clusters") {
		t.Errorf("Help = %q", v.Help())
	}
}

func TestClusterDetailViewSelected(t *testing.T) {
	v := ClusterDetailView{Detail: sampleDetail().Move(1)}
	if got := v.Lines()[v.Selected()]; !strings.HasPrefix(got, "gros-2") {
		t.Errorf("selected line = %q, want the gros-2 row", got)
	}
}

func TestClusterDetailViewLoading(t *testing.T) {
	v := ClusterDetailView{Detail: models.NewClusterDetail("nancy", models.Cluster{UID: "gros", Model: "Dell"})}
	lines := v.Lines()
	if len(lines) != 11 || !strings.Contains(lines[2], "CPU         loading") || !strings.Contains(lines[9], "NODES       loading") || v.Selected() != -1 {
		t.Errorf("while loading only the info is shown: %q selected=%d", lines, v.Selected())
	}
	if s := Render(v, Status{Loading: true}, 100, 24); !strings.Contains(s, "Dell") || !strings.Contains(s, "loading…") {
		t.Errorf("loading screen:\n%s", s)
	}
}

func TestClusterDetailKeepsInfoOnScreenWhileScrolling(t *testing.T) {
	s := Render(ClusterDetailView{Detail: manyNodes(200).Move(150)}, Status{}, 100, 24)
	for _, want := range []string{"NODES       200", "NODE ", "big-151 "} {
		if !strings.Contains(s, want) {
			t.Errorf("screen missing %q:\n%s", want, s)
		}
	}
	if strings.Contains(s, "big-1 ") || strings.Contains(s, "big-152 ") {
		t.Errorf("should be scrolled so big-151 is the last row:\n%s", s)
	}
}

func TestJobText(t *testing.T) {
	cases := []struct {
		r    models.Reservation
		want string
	}{
		{models.Reservation{JobID: 1, User: "a", State: "Running", Start: at(-1), End: at(1)}, "#1 a 13:30→15:30 (2h) Running"},
		{models.Reservation{JobID: 2, User: "b", Start: at(1), End: at(2.5)}, "next #2 b 15:30→17:00 (1h30m)"},
		{models.Reservation{JobID: 3, User: "c", Start: at(20), End: at(21)}, "next #3 c Mon 23 10:30→Mon 23 11:30 (1h)"},
		{models.Reservation{JobID: 4, User: "d", Queue: "besteffort", State: "Running", Start: at(-1), End: at(0.75)}, "#4 d 13:30→15:15 (1h45m) besteffort Running"},
	}
	for _, c := range cases {
		n := models.NodeStatus{Hard: "alive", Reservations: []models.Reservation{c.r}}
		if got := job(n, now); got != c.want {
			t.Errorf("job = %q, want %q", got, c.want)
		}
	}
	if job(models.NodeStatus{}, now) != "" {
		t.Error("no jobs: empty")
	}
}

func TestHardwareText(t *testing.T) {
	a100 := models.GPU{Vendor: "Nvidia", Model: "A100", MemoryBytes: 40 << 30}
	cases := []struct{ got, want string }{
		{gpus([]models.GPU{a100, a100, a100, a100}), "4 × Nvidia A100 40 GiB"},
		{gpus([]models.GPU{a100, {Vendor: "AMD", Model: "MI50"}}), "Nvidia A100 40 GiB · AMD MI50"},
		{gpus(nil), ""},
		{nics([]models.NIC{{Interface: "Ethernet", RateBps: 25e9}, {Interface: "InfiniBand", RateBps: 100e9}}), "25 Gbps Ethernet · 100 Gbps InfiniBand"},
		{disks([]models.Disk{{Kind: "HDD", Bytes: 2e12}}), "2 TB HDD"},
		{bytesIEC(512 << 20), "512 MiB"},
		{bytesIEC(1536 << 30), "1.5 TiB"},
		{rate(1e9), "1 Gbps"},
		{cpu(models.Hardware{CPU: "AMD EPYC 7452", Sockets: 2, Cores: 64}), "2 × AMD EPYC 7452 · 64 cores"},
		{bytesSI(0), ""},
	}
	for _, c := range cases {
		if c.got != c.want {
			t.Errorf("got %q, want %q", c.got, c.want)
		}
	}
}
