package views

import (
	"slices"
	"strings"
	"testing"

	"grid-tui/models"
)

// sampleSites are made-up rows for tests only.
func sampleSites() models.Sites {
	return models.NewSites([]models.Site{
		{UID: "nancy", Name: "Nancy", Description: "Grid5000 Nancy site"},
		{UID: "rennes", Name: "Rennes", Description: "Grid5000 Rennes site"},
	})
}

func TestSitesViewTable(t *testing.T) {
	v := SitesView{Sites: sampleSites()}
	want := []string{
		"SITE     NAME     DESCRIPTION",
		"nancy    Nancy    Grid5000 Nancy site",
		"rennes   Rennes   Grid5000 Rennes site",
	}
	// Without a terminal Lip Gloss draws no colours, so the header is plain text.
	if got := v.Lines(); !slices.Equal(got, want) {
		t.Errorf("Lines =\n%s\nwant\n%s", strings.Join(got, "\n"), strings.Join(want, "\n"))
	}
	if got := v.Labels(); !slices.Equal(got, []string{"sites: 2"}) {
		t.Errorf("Labels = %q", got)
	}
	if got := v.Command(); got != "curl https://api.grid5000.fr/stable/sites" {
		t.Errorf("Command = %q", got)
	}
}

func TestSitesViewEmpty(t *testing.T) {
	v := SitesView{Sites: models.NewSites(nil)}
	if v.Lines() != nil {
		t.Errorf("no sites should have no lines, got %q", v.Lines())
	}
	s := Render(v, Status{}, 100, 24)
	if !strings.Contains(s, "sites: 0") || !strings.Contains(s, emptyText) {
		t.Errorf("empty sites:\n%s", s)
	}
}

func TestSitesViewOnScreen(t *testing.T) {
	s := Render(SitesView{Sites: sampleSites()}, Status{}, 100, 24)
	for _, want := range []string{"sites: 2", "SITE", "nancy    Nancy    Grid5000 Nancy site", "$ curl https://api.grid5000.fr/stable/sites"} {
		if !strings.Contains(s, want) {
			t.Errorf("screen missing %q:\n%s", want, s)
		}
	}
}
