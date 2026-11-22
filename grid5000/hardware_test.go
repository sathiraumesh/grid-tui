package grid5000

import (
	"context"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"

	"grid-tui/models"
)

func TestClusterHardware(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/sites/nancy/clusters/gros/nodes":
			w.Write([]byte(`{"total":2,"offset":0,"items":[{
				"uid":"gros-1",
				"processor":{"model":"Intel Xeon","other_description":"Intel Xeon Gold 5220","clock_speed":2200000000},
				"architecture":{"nb_procs":1,"nb_cores":18,"nb_threads":36},
				"main_memory":{"ram_size":103079215104},
				"storage_devices":[{"storage":"SSD","interface":"SATA","model":"MZ7KH480HAHQ0D3","size":480103981056},
				                   {"storage":"SSD","interface":"SATA","model":"MZ7KH960HAJR0D3","size":960197124096}],
				"network_adapters":[{"interface":"Ethernet","rate":25000000000,"mounted":true},
				                    {"interface":"Ethernet","rate":25000000000,"mounted":false}],
				"gpu_devices":{"1":{"vendor":"Nvidia","model":"A100","memory":42949672960},
				               "0":{"vendor":"Nvidia","model":"A100","memory":42949672960}}
			},{"uid":"gros-2"}]}`))
		case "/sites/nancy/clusters/empty/nodes":
			w.Write([]byte(`{"total":0,"offset":0,"items":[]}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()
	c := &Client{BaseURL: srv.URL}

	got, err := c.ClusterHardware(context.Background(), "nancy", "gros")
	if err != nil {
		t.Fatal(err)
	}
	a100 := models.GPU{Vendor: "Nvidia", Model: "A100", MemoryBytes: 42949672960}
	want := models.Hardware{
		Nodes: 2,
		CPU:   "Intel Xeon Gold 5220", Sockets: 1, Cores: 18, Threads: 36, ClockGHz: 2.2,
		MemoryBytes: 103079215104,
		Disks: []models.Disk{
			{Kind: "SSD", Interface: "SATA", Model: "MZ7KH480HAHQ0D3", Bytes: 480103981056},
			{Kind: "SSD", Interface: "SATA", Model: "MZ7KH960HAJR0D3", Bytes: 960197124096},
		},
		NICs: []models.NIC{{Interface: "Ethernet", RateBps: 25000000000}}, // the unmounted one is left out
		GPUs: []models.GPU{a100, a100},
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("hardware =\n%+v\nwant\n%+v", got, want)
	}

	if _, err := c.ClusterHardware(context.Background(), "nancy", "empty"); err == nil {
		t.Error("a cluster with no nodes should be an error")
	}
	if _, err := c.ClusterHardware(context.Background(), "nancy", ""); err == nil {
		t.Error("an empty cluster name should be an error")
	}
}

func TestHardwareFallsBackToTheProcessorModel(t *testing.T) {
	var n nodeDescription
	n.Processor.Model = "AMD EPYC"
	if h := hardwareOf(n); h.CPU != "AMD EPYC" || !(models.Hardware{}).IsZero() || h.IsZero() {
		t.Errorf("hardware = %+v", h)
	}
}
