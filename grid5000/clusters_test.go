package grid5000

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"slices"
	"testing"
)

// clustersAPI answers GET /sites/nancy/clusters like the Grid'5000 API.
func clustersAPI(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/sites/nancy/clusters":
			// Abridged: extra fields are ignored.
			w.Write([]byte(`{"total":2,"offset":0,"items":[
				{"uid":"graffiti","model":"Dell PowerEdge T640","queues":["production","admin"],"type":"cluster","links":[]},
				{"uid":"gros","model":"Dell PowerEdge R640","queues":["default","admin"],"type":"cluster","links":[]}
			],"links":[]}`))
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func TestClusters(t *testing.T) {
	c := &Client{BaseURL: clustersAPI(t).URL}
	got, err := c.Clusters(context.Background(), "nancy")
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("got %d clusters, want 2: %+v", len(got), got)
	}
	if got[1].UID != "gros" || got[1].Model != "Dell PowerEdge R640" || !slices.Equal(got[1].Queues, []string{"default", "admin"}) {
		t.Errorf("gros decoded wrong: %+v", got[1])
	}
}

func TestClustersUnknownSite(t *testing.T) {
	c := &Client{BaseURL: clustersAPI(t).URL}
	_, err := c.Clusters(context.Background(), "atlantis")

	var apiErr *Error
	if !errors.As(err, &apiErr) || apiErr.Status != http.StatusNotFound || apiErr.Path != "/sites/atlantis/clusters" {
		t.Fatalf("err = %v, want a 404 *Error for /sites/atlantis/clusters", err)
	}
}

func TestClustersNoSite(t *testing.T) {
	if _, err := (&Client{BaseURL: "http://unused"}).Clusters(context.Background(), ""); err == nil {
		t.Fatal("an empty site should be an error, not a call to /sites//clusters")
	}
}

func TestClustersPath(t *testing.T) {
	if got := ClustersPath("nancy"); got != "/sites/nancy/clusters" {
		t.Errorf("ClustersPath = %q", got)
	}
	if got := ClustersPath("a/b"); got != "/sites/a%2Fb/clusters" {
		t.Errorf("a site name must not change the path: %q", got)
	}
}
