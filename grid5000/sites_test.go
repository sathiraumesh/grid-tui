package grid5000

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"slices"
	"strings"
	"testing"

	"grid-tui/models"
)

// fakeAPI answers like the Grid'5000 API, and wants basic auth alice/secret.
func fakeAPI(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if u, p, ok := r.BasicAuth(); !ok || u != "alice" || p != "secret" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		switch r.URL.Path {
		case "/sites":
			// Abridged from the real answer: extra fields are ignored.
			w.Write([]byte(`{"total":2,"offset":0,"items":[
				{"uid":"nancy","name":"Nancy","description":"Grid5000 Nancy site","type":"site","links":[]},
				{"uid":"rennes","name":"Rennes","description":"Grid5000 Rennes site","type":"site","links":[]}
			],"links":[]}`))
		case "/broken/sites":
			w.Write([]byte(`{not json`))
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func TestSites(t *testing.T) {
	srv := fakeAPI(t)
	c := &Client{BaseURL: srv.URL, User: "alice", Password: "secret"}

	got, err := c.Sites(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	want := []models.Site{
		{UID: "nancy", Name: "Nancy", Description: "Grid5000 Nancy site"},
		{UID: "rennes", Name: "Rennes", Description: "Grid5000 Rennes site"},
	}
	if !slices.Equal(got, want) {
		t.Errorf("Sites = %+v, want %+v", got, want)
	}
}

func TestSitesUnauthorized(t *testing.T) {
	srv := fakeAPI(t)
	_, err := (&Client{BaseURL: srv.URL}).Sites(context.Background())

	var apiErr *Error
	if !errors.As(err, &apiErr) || apiErr.Status != http.StatusUnauthorized || apiErr.Path != "/sites" {
		t.Fatalf("err = %v, want a 401 *Error for /sites", err)
	}
	if !strings.Contains(err.Error(), "G5K_USER") {
		t.Errorf("a 401 should say how to log in: %v", err)
	}
}

func TestSitesBadJSON(t *testing.T) {
	srv := fakeAPI(t)
	c := &Client{BaseURL: srv.URL + "/broken", User: "alice", Password: "secret"}
	if _, err := c.Sites(context.Background()); err == nil || !strings.Contains(err.Error(), "reading the answer") {
		t.Fatalf("err = %v, want a decode error", err)
	}
}

func TestNewClientFromEnv(t *testing.T) {
	t.Setenv("G5K_USER", "bob")
	t.Setenv("G5K_PASSWORD", "pw")
	t.Setenv("G5K_API", "https://example.test/api/")
	c := NewClient()
	if c.User != "bob" || c.Password != "pw" || c.BaseURL != "https://example.test/api" {
		t.Errorf("client = %+v", c)
	}

	t.Setenv("G5K_API", "")
	if NewClient().BaseURL != DefaultBaseURL {
		t.Errorf("default base URL should be %s", DefaultBaseURL)
	}
}
