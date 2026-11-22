package grid5000

import (
	"context"
	"net/http"
	"net/http/httptest"
	"sort"
	"testing"
	"time"

	"grid-tui/models"
)

func TestClusterStatus(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/sites/nancy/clusters/gros/status" {
			http.NotFound(w, r)
			return
		}
		w.Write([]byte(`{"nodes":{
			"gros-1.nancy.grid5000.fr":{"hard":"alive","soft":"busy","reservations":[
				{"uid":4521,"user":"bob","queue":"default","state":"Running","walltime":7200,"started_at":1800000000,"scheduled_at":1800000000},
				{"uid":"4600","user":"eve","queue":"default","state":"Waiting","walltime":"3600","started_at":null,"scheduled_at":1800010000},
				{"uid":4700,"user":"x","queue":"default","state":"Waiting","walltime":3600,"started_at":null,"scheduled_at":null}
			]},
			"gros-2.nancy.grid5000.fr":{"hard":"dead","soft":"unknown","reservations":[]}
		},"disks":{}}`))
	}))
	defer srv.Close()

	nodes, err := (&Client{BaseURL: srv.URL}).ClusterStatus(context.Background(), "nancy", "gros")
	if err != nil {
		t.Fatal(err)
	}
	sort.Slice(nodes, func(i, j int) bool { return nodes[i].Name < nodes[j].Name })
	if len(nodes) != 2 || nodes[0].Name != "gros-1" || nodes[1].Hard != "dead" {
		t.Fatalf("nodes = %+v", nodes)
	}
	res := nodes[0].Reservations
	if len(res) != 2 {
		t.Fatalf("want 2 reservations (the unscheduled one left out), got %+v", res)
	}
	want := []models.Reservation{
		{JobID: 4521, User: "bob", Queue: "default", State: "Running", Start: time.Unix(1800000000, 0), End: time.Unix(1800007200, 0)},
		{JobID: 4600, User: "eve", Queue: "default", State: "Waiting", Start: time.Unix(1800010000, 0), End: time.Unix(1800013600, 0)},
	}
	for i := range want {
		if res[i] != want[i] {
			t.Errorf("reservation %d = %+v, want %+v", i, res[i], want[i])
		}
	}
}

func TestStatusPath(t *testing.T) {
	if got := StatusPath("nancy", "gros"); got != "/sites/nancy/clusters/gros/status" {
		t.Errorf("StatusPath = %q", got)
	}
}

func TestClusterStatusNeedsSiteAndCluster(t *testing.T) {
	if _, err := (&Client{BaseURL: "http://unused"}).ClusterStatus(context.Background(), "nancy", ""); err == nil {
		t.Fatal("an empty cluster should be an error")
	}
}
