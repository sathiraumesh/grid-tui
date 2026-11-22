package models

import (
	"slices"
	"testing"
)

// field is the index of the search field with key.
func field(t *testing.T, key string) int {
	t.Helper()
	for i, f := range SearchFields {
		if f.Key == key {
			return i
		}
	}
	t.Fatalf("no field %q", key)
	return -1
}

func loadedCluster(uid string, h Hardware, metrics ...string) Cluster {
	c := Cluster{UID: uid, Hardware: h, HardwareState: HardwareLoaded}
	for _, m := range metrics {
		c.Metrics = append(c.Metrics, Metric{Name: m})
	}
	return c
}

// sampleSearch: lyon has a GPU cluster with a wattmeter; nancy an Intel
// cluster, an AMD one, and one whose hardware didn't load.
func sampleSearch() Search {
	a100 := GPU{Vendor: "Nvidia", Model: "A100", MemoryBytes: 40 << 30}
	s := NewSearch(2)
	s = s.WithSite("nancy", []Cluster{
		loadedCluster("gros", Hardware{Nodes: 124, CPU: "Intel Xeon Gold 5220", Cores: 18, MemoryBytes: 96 << 30,
			Disks: []Disk{{Kind: "SSD", Interface: "SATA"}}, NICs: []NIC{{RateBps: 25e9}}}),
		loadedCluster("grat", Hardware{Nodes: 8, CPU: "AMD EPYC 7513", Cores: 64, MemoryBytes: 512 << 30,
			Disks: []Disk{{Kind: "SSD", Interface: "NVME"}}, NICs: []NIC{{RateBps: 100e9}}}),
		{UID: "grvingt"}, // hardware still loading
	})
	return s.WithSite("lyon", []Cluster{
		loadedCluster("gemini", Hardware{Nodes: 2, CPU: "Intel Xeon E5-2698", Cores: 40, MemoryBytes: 512 << 30,
			GPUs: []GPU{a100, a100}, Disks: []Disk{{Kind: "HDD", Interface: "SAS"}}}, "wattmetre_power_watt"),
	})
}

func names(es []SearchEntry) []string {
	out := make([]string, len(es))
	for i, e := range es {
		out[i] = e.Site + "/" + e.Cluster.UID
	}
	return out
}

// set chooses an option of a choice field by cycling to it.
func set(t *testing.T, s Search, key, option string) Search {
	t.Helper()
	s.Focus = field(t, key)
	for range len(s.Options(s.Focus)) {
		if s.Value(s.Focus) == option || (option == Any && s.Value(s.Focus) == "") {
			return s
		}
		s = s.Cycle(1)
	}
	t.Fatalf("%s has no option %q: %q", key, option, s.Options(s.Focus))
	return s
}

// tick ticks a flag.
func tick(t *testing.T, s Search, key string) Search {
	t.Helper()
	s.Focus = field(t, key)
	return s.Toggle()
}

// typeIn types digits into a number field.
func typeIn(t *testing.T, s Search, key, digits string) Search {
	t.Helper()
	s.Focus = field(t, key)
	for _, r := range digits {
		s = s.Type(r)
	}
	return s
}

func TestSearchWithNothingSetFindsEverything(t *testing.T) {
	s := sampleSearch()
	want := []string{"lyon/gemini", "nancy/grat", "nancy/gros", "nancy/grvingt"}
	if got := names(s.Results()); !slices.Equal(got, want) {
		t.Errorf("results = %v, want %v", got, want)
	}
	if s.Loading() {
		t.Error("both sites are done")
	}
}

func TestSearchOptionsComeFromTheData(t *testing.T) {
	s := sampleSearch()
	cases := map[string][]string{
		"site": {Any, "lyon", "nancy"},
		"cpu":  {Any, "AMD", "Intel"},
		"gpu":  {Any, "Nvidia A100"},
	}
	for key, want := range cases {
		if got := s.Options(field(t, key)); !slices.Equal(got, want) {
			t.Errorf("%s options = %q, want %q", key, got, want)
		}
	}
}

func TestSearchRequirements(t *testing.T) {
	cases := []struct {
		name string
		set  func(Search) Search
		want []string
	}{
		{"site", func(s Search) Search { return set(t, s, "site", "lyon") }, []string{"lyon/gemini"}},
		{"cpu", func(s Search) Search { return set(t, s, "cpu", "Intel") }, []string{"lyon/gemini", "nancy/gros"}},
		{"has GPU", func(s Search) Search { return tick(t, s, "hasgpu") }, []string{"lyon/gemini"}},
		{"GPU model", func(s Search) Search { return set(t, s, "gpu", "Nvidia A100") }, []string{"lyon/gemini"}},
		{"disk NVME", func(s Search) Search { return set(t, s, "disk", "NVME") }, []string{"nancy/grat"}},
		{"disk SSD", func(s Search) Search { return set(t, s, "disk", "SSD") }, []string{"nancy/grat", "nancy/gros"}},
		{"wattmeter", func(s Search) Search { return tick(t, s, "wattmeter") }, []string{"lyon/gemini"}},
		{"cores", func(s Search) Search { return typeIn(t, s, "cores", "40") }, []string{"lyon/gemini", "nancy/grat"}},
		{"memory", func(s Search) Search { return typeIn(t, s, "mem", "500") }, []string{"lyon/gemini", "nancy/grat"}},
		{"nodes", func(s Search) Search { return typeIn(t, s, "nodes", "10") }, []string{"nancy/gros"}},
		{"GPU memory", func(s Search) Search { return typeIn(t, s, "gpumem", "40") }, []string{"lyon/gemini"}},
		{"network", func(s Search) Search { return typeIn(t, s, "net", "50") }, []string{"nancy/grat"}},
		{"together", func(s Search) Search { return typeIn(t, set(t, s, "cpu", "Intel"), "cores", "20") }, []string{"lyon/gemini"}},
	}
	for _, c := range cases {
		if got := names(c.set(sampleSearch()).Results()); !slices.Equal(got, c.want) {
			t.Errorf("%s: results = %v, want %v", c.name, got, c.want)
		}
	}
}

func TestSearchCycleWrapsAndBackToAny(t *testing.T) {
	s := sampleSearch()
	s.Focus = field(t, "site")
	s = s.Cycle(1) // lyon
	if s.Value(s.Focus) != "lyon" {
		t.Fatalf("value = %q", s.Value(s.Focus))
	}
	s = s.Cycle(-1) // any
	if s.Value(s.Focus) != "" {
		t.Errorf("back to any: %q", s.Value(s.Focus))
	}
	s = s.Cycle(-1) // wraps to the last: nancy
	if s.Value(s.Focus) != "nancy" {
		t.Errorf("wrap: %q", s.Value(s.Focus))
	}
}

func TestSearchTypeAndBackspace(t *testing.T) {
	s := typeIn(t, sampleSearch(), "cores", "3a2")
	if v := s.Value(s.Focus); v != "32" {
		t.Errorf("only digits: %q", v)
	}
	if s = s.Backspace(); s.Value(s.Focus) != "3" {
		t.Errorf("backspace: %q", s.Value(s.Focus))
	}
	s.Focus = field(t, "site")
	if s.Type('5').Value(s.Focus) != "" {
		t.Error("typing on a choice does nothing")
	}
}

func TestSearchFocusMovesIntoTheResults(t *testing.T) {
	s := sampleSearch().Move(len(SearchFields)) // the first result
	if _, onField := s.FocusedField(); onField {
		t.Fatal("focus should be on a result")
	}
	if e, ok := s.Selected(); !ok || e.Cluster.UID != "gemini" {
		t.Errorf("selected = %+v", e)
	}
	s = s.Move(100)
	if e, _ := s.Selected(); e.Cluster.UID != "grvingt" {
		t.Errorf("last result = %+v", e)
	}
}

func TestSearchValuesAreNotShared(t *testing.T) {
	a := typeIn(t, sampleSearch(), "cores", "1")
	b := a.Type('2')
	if a.Value(a.Focus) != "1" || b.Value(b.Focus) != "12" {
		t.Errorf("a=%q b=%q", a.Value(a.Focus), b.Value(b.Focus))
	}
}

func TestSearchWithSiteReplacesThatSite(t *testing.T) {
	s := sampleSearch().WithSite("lyon", nil)
	if got := names(s.Results()); slices.Contains(got, "lyon/gemini") {
		t.Errorf("lyon's clusters should be replaced: %v", got)
	}
}

func TestSearchToggle(t *testing.T) {
	s := tick(t, sampleSearch(), "hasgpu")
	if s.Value(s.Focus) != Ticked {
		t.Fatalf("ticked: %q", s.Value(s.Focus))
	}
	if s = s.Toggle(); s.Value(s.Focus) != "" {
		t.Errorf("unticked: %q", s.Value(s.Focus))
	}
	if s = s.Cycle(1); s.Value(s.Focus) != Ticked {
		t.Errorf("←→ on a flag toggles it too: %q", s.Value(s.Focus))
	}
	s.Focus = field(t, "site")
	if s.Toggle().Value(s.Focus) != "" {
		t.Error("toggling a choice does nothing")
	}
}
