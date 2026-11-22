package views

import (
	"strings"
	"testing"

	"grid-tui/models"
)

// sampleSearch: two sites loaded, lyon's gemini has GPUs and a wattmeter.
func sampleSearch() models.Search {
	gemini := models.Cluster{UID: "gemini", HardwareState: models.HardwareLoaded,
		Metrics:  []models.Metric{{Name: "wattmetre_power_watt"}},
		Hardware: models.Hardware{Nodes: 2, CPU: "Intel Xeon E5-2698", Sockets: 2, Cores: 40, MemoryBytes: 512 << 30, GPUs: []models.GPU{{Vendor: "Nvidia", Model: "V100"}}}}
	gros := models.Cluster{UID: "gros", HardwareState: models.HardwareLoaded,
		Hardware: models.Hardware{Nodes: 124, CPU: "Intel Xeon Gold 5220", Sockets: 1, Cores: 18, MemoryBytes: 96 << 30}}
	return models.NewSearch(2).WithSite("lyon", []models.Cluster{gemini}).WithSite("nancy", []models.Cluster{gros})
}

// focusOn puts the focus on the field with key.
func focusOn(s models.Search, key string) models.Search {
	for i, f := range models.SearchFields {
		if f.Key == key {
			s.Focus = i
		}
	}
	return s
}

func TestSearchViewForm(t *testing.T) {
	s := focusOn(sampleSearch(), "hasgpu").Toggle()
	lines := SearchView{Search: s}.Lines()
	if !strings.HasPrefix(lines[0], "▸ Has GPU") || !strings.HasSuffix(lines[0], "[x]") {
		t.Errorf("focused, ticked flag: %q", lines[0])
	}
	if !strings.HasPrefix(lines[1], "  Wattmeter") || !strings.HasSuffix(lines[1], "[ ]") {
		t.Errorf("unticked flag: %q", lines[1])
	}
	if !strings.Contains(lines[2], "Site") || !strings.HasSuffix(lines[2], "◀ any ▶") {
		t.Errorf("choice: %q", lines[2])
	}
	if !strings.HasSuffix(lines[6], "[      ]") {
		t.Errorf("empty number: %q", lines[6])
	}
}

func TestSearchViewResults(t *testing.T) {
	s := focusOn(sampleSearch(), "hasgpu").Toggle()
	v := SearchView{Search: s}
	lines := v.Lines()
	header := lines[len(models.SearchFields)+1]
	if !strings.HasPrefix(header, "SITE") || !strings.Contains(header, "CLUSTER") || !strings.Contains(header, "WATTMETER") {
		t.Errorf("header = %q", header)
	}
	results := lines[v.Pinned():]
	if len(results) != 1 || !strings.HasPrefix(results[0], "lyon   gemini") || !strings.HasSuffix(results[0], "yes") {
		t.Errorf("results = %q", results)
	}
	if got := v.Labels(); got[1] != "matches: 1 of 2" || len(got) != 2 {
		t.Errorf("labels = %q", got)
	}
}

func TestSearchViewNoMatch(t *testing.T) {
	s := focusOn(sampleSearch(), "cores")
	for _, r := range "999" {
		s = s.Type(r)
	}
	lines := SearchView{Search: s}.Lines()
	if last := lines[len(lines)-1]; !strings.Contains(last, "no cluster meets these requirements") {
		t.Errorf("last line = %q", last)
	}
	loading := models.NewSearch(3)
	loadingLines := SearchView{Search: loading}.Lines()
	if last := loadingLines[len(loadingLines)-1]; !strings.Contains(last, "loading the clusters") {
		t.Errorf("while loading: %q", last)
	}
	got := SearchView{Search: loading}.Labels()
	if got[len(got)-1] != "loading sites 0/3" {
		t.Errorf("labels while loading = %q", got)
	}
}

func TestSearchViewSelectedAndHelp(t *testing.T) {
	s := sampleSearch()
	v := SearchView{Search: focusOn(s, "cores")}
	if !strings.Contains(v.Lines()[v.Selected()], "Min cores") || !strings.Contains(v.Help(), "type a number") {
		t.Errorf("on a number field: selected %q, help %q", v.Lines()[v.Selected()], v.Help())
	}
	v = SearchView{Search: s.Move(len(models.SearchFields) + 1)} // the second result
	if got := v.Lines()[v.Selected()]; !strings.HasPrefix(got, "nancy") || !strings.Contains(v.Help(), "enter details") {
		t.Errorf("on a result: selected %q, help %q", got, v.Help())
	}
	if !strings.Contains((SearchView{Search: focusOn(s, "site")}).Help(), "choose") ||
		!strings.Contains((SearchView{Search: focusOn(s, "wattmeter")}).Help(), "tick") {
		t.Error("help should match the field")
	}
}

func TestSearchViewOnScreen(t *testing.T) {
	out := Render(SearchView{Search: sampleSearch()}, Status{}, 120, 30)
	for _, want := range []string{"search", "matches: 2 of 2", "Has GPU", "gemini", "gros", "$ curl"} {
		if !strings.Contains(out, want) {
			t.Errorf("screen missing %q:\n%s", want, out)
		}
	}
}
