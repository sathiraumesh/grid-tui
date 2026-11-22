package models

import (
	"sort"
	"strconv"
	"strings"
)

// Search finds the clusters of every site that meet a set of
// requirements, picked in a form: tick boxes (enter), choices (enter or
// ←→) and minimum numbers (typed). The results are the clusters that meet
// all of them.
type Search struct {
	Entries    []SearchEntry // every cluster known so far, sorted by site then cluster
	SitesTotal int           // sites being loaded
	SitesDone  int           // sites loaded (or failed)

	values []string // per field of SearchFields: the choice or the typed number; "" = any
	Focus  int      // a field (< len(SearchFields)), or a result (Focus - len(SearchFields))
}

var _ Model = Search{} // Search implements Model

// SearchEntry is one cluster of one site.
type SearchEntry struct {
	Site    string
	Cluster Cluster
}

// FieldKind is how a search field is filled in.
type FieldKind int

const (
	FieldFlag   FieldKind = iota // a tick box: required or not
	FieldChoice                  // one of its options
	FieldNumber                  // a minimum, typed
)

// SearchField is one requirement of the form.
type SearchField struct {
	Key   string
	Label string
	Kind  FieldKind
}

// Any is the first option of every choice: no requirement.
const Any = "any"

// Ticked is the value of a ticked flag.
const Ticked = "yes"

// The fields of the form, top to bottom.
var SearchFields = []SearchField{
	{"hasgpu", "Has GPU", FieldFlag},
	{"wattmeter", "Wattmeter", FieldFlag},
	{"site", "Site", FieldChoice},
	{"cpu", "CPU", FieldChoice},
	{"gpu", "GPU model", FieldChoice},
	{"disk", "Disk", FieldChoice},
	{"nodes", "Min nodes", FieldNumber},
	{"cores", "Min cores / node", FieldNumber},
	{"mem", "Min memory (GiB)", FieldNumber},
	{"gpumem", "Min GPU memory (GiB)", FieldNumber},
	{"net", "Min network (Gbps)", FieldNumber},
}

// NewSearch makes an empty search that is about to load sites sites.
func NewSearch(sites int) Search {
	return Search{SitesTotal: sites, values: make([]string, len(SearchFields))}
}

// Loading is whether some sites are still being loaded.
func (s Search) Loading() bool { return s.SitesDone < s.SitesTotal }

// WithSite stores the clusters of one site (entries may be nil if it
// failed) and counts it as done.
func (s Search) WithSite(site string, clusters []Cluster) Search {
	entries := make([]SearchEntry, 0, len(s.Entries)+len(clusters))
	for _, e := range s.Entries {
		if e.Site != site {
			entries = append(entries, e)
		}
	}
	for _, c := range clusters {
		entries = append(entries, SearchEntry{Site: site, Cluster: c})
	}
	sort.SliceStable(entries, func(i, j int) bool {
		if entries[i].Site != entries[j].Site {
			return entries[i].Site < entries[j].Site
		}
		return entries[i].Cluster.UID < entries[j].Cluster.UID
	})
	s.Entries = entries
	s.SitesDone = min(s.SitesDone+1, s.SitesTotal)
	return s.Move(0)
}

// Value is what field i is set to: an option, a typed number, or "" (any).
func (s Search) Value(i int) string {
	if i < 0 || i >= len(s.values) {
		return ""
	}
	return s.values[i]
}

// with returns s with field i set to v. The values are copied: other
// copies of the model keep theirs.
func (s Search) with(i int, v string) Search {
	values := make([]string, len(SearchFields))
	copy(values, s.values)
	values[i] = v
	s.values = values
	return s.Move(0) // the results may be fewer: keep the focus inside
}

// FocusedField is the field the focus is on, or false if it is on a result.
func (s Search) FocusedField() (int, bool) {
	return s.Focus, s.Focus < len(SearchFields)
}

// Options are the choices of field i, built from the clusters loaded:
// "any" first, then what was found.
func (s Search) Options(i int) []string {
	opts := []string{Any}
	switch SearchFields[i].Key {
	case "site":
		opts = append(opts, s.distinct(func(e SearchEntry) []string { return []string{e.Site} })...)
	case "cpu":
		opts = append(opts, s.distinct(func(e SearchEntry) []string { return []string{cpuVendor(e.Cluster.Hardware.CPU)} })...)
	case "gpu":
		opts = append(opts, s.distinct(func(e SearchEntry) []string {
			var names []string
			for _, g := range e.Cluster.Hardware.GPUs {
				names = append(names, gpuName(g))
			}
			return names
		})...)
	case "disk":
		opts = append(opts, "SSD", "HDD", "NVME")
	}
	return opts
}

// distinct is the different non-empty values of get over the entries, sorted.
func (s Search) distinct(get func(SearchEntry) []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, e := range s.Entries {
		for _, v := range get(e) {
			if v != "" && !seen[v] {
				seen[v] = true
				out = append(out, v)
			}
		}
	}
	sort.Strings(out)
	return out
}

// Toggle ticks or unticks the focused flag.
func (s Search) Toggle() Search {
	i, ok := s.FocusedField()
	if !ok || SearchFields[i].Kind != FieldFlag {
		return s
	}
	if s.Value(i) == Ticked {
		return s.with(i, "")
	}
	return s.with(i, Ticked)
}

// Cycle moves the choice of the focused field by step through its
// options; on a flag it toggles it.
func (s Search) Cycle(step int) Search {
	i, ok := s.FocusedField()
	if ok && SearchFields[i].Kind == FieldFlag {
		return s.Toggle()
	}
	if !ok || SearchFields[i].Kind != FieldChoice {
		return s
	}
	opts := s.Options(i)
	cur := 0
	for j, o := range opts {
		if o == s.Value(i) {
			cur = j
		}
	}
	next := ((cur+step)%len(opts) + len(opts)) % len(opts) // wraps around
	v := opts[next]
	if v == Any {
		v = ""
	}
	return s.with(i, v)
}

// Type adds r to the focused number field. Only digits are taken.
func (s Search) Type(r rune) Search {
	i, ok := s.FocusedField()
	if !ok || SearchFields[i].Kind != FieldNumber || r < '0' || r > '9' || len(s.Value(i)) >= 6 {
		return s
	}
	return s.with(i, s.Value(i)+string(r))
}

// Backspace removes the last digit of the focused number field.
func (s Search) Backspace() Search {
	i, ok := s.FocusedField()
	if !ok || SearchFields[i].Kind != FieldNumber || s.Value(i) == "" {
		return s
	}
	v := s.Value(i)
	return s.with(i, v[:len(v)-1])
}

// Results are the clusters that meet every requirement.
func (s Search) Results() []SearchEntry {
	var out []SearchEntry
	for _, e := range s.Entries {
		if s.Match(e) {
			out = append(out, e)
		}
	}
	return out
}

// Len is how many clusters meet the requirements.
func (s Search) Len() int { return len(s.Results()) }

// Move moves the focus by step, through the fields and then the results.
func (s Search) Move(step int) Search {
	s.Focus = moveCursor(s.Focus, step, len(SearchFields)+s.Len())
	return s
}

// Selected is the result the focus is on, or false if it is on a field.
func (s Search) Selected() (SearchEntry, bool) {
	r := s.Results()
	i := s.Focus - len(SearchFields)
	if i < 0 || i >= len(r) {
		return SearchEntry{}, false
	}
	return r[i], true
}

// Match is whether e meets every requirement set. A requirement on the
// hardware is not met while the cluster's hardware is unknown.
func (s Search) Match(e SearchEntry) bool {
	h, known := e.Cluster.Hardware, e.Cluster.HardwareState == HardwareLoaded
	for i, f := range SearchFields {
		v := s.Value(i)
		if v == "" {
			continue
		}
		if f.Key != "site" && f.Key != "wattmeter" && !known { // site and wattmeter aren't hardware
			return false
		}
		if !matchField(f.Key, v, e, h) {
			return false
		}
	}
	return true
}

func matchField(key, v string, e SearchEntry, h Hardware) bool {
	switch key {
	case "site":
		return e.Site == v
	case "cpu":
		return cpuVendor(h.CPU) == v
	case "hasgpu":
		return len(h.GPUs) > 0
	case "wattmeter":
		return e.Cluster.Wattmeter()
	case "gpu":
		for _, g := range h.GPUs {
			if gpuName(g) == v {
				return true
			}
		}
		return false
	case "disk":
		for _, d := range h.Disks {
			if strings.EqualFold(d.Kind, v) || strings.EqualFold(d.Interface, v) {
				return true
			}
		}
		return false
	}
	// The numbers: the cluster must have at least v.
	want, err := strconv.ParseFloat(v, 64)
	if err != nil {
		return true
	}
	var got float64
	switch key {
	case "nodes":
		got = float64(h.Nodes)
	case "cores":
		got = float64(h.Cores)
	case "mem":
		got = float64(h.MemoryBytes) / (1 << 30)
	case "gpumem":
		for _, g := range h.GPUs {
			got = max(got, float64(g.MemoryBytes)/(1<<30))
		}
	case "net":
		for _, n := range h.NICs {
			got = max(got, float64(n.RateBps)/1e9)
		}
	}
	return got >= want
}

// cpuVendor is the first word of a CPU name: "Intel", "AMD", "Neoverse-V2".
func cpuVendor(cpu string) string {
	first, _, _ := strings.Cut(strings.TrimSpace(cpu), " ")
	return first
}

// gpuName is e.g. "Nvidia A100".
func gpuName(g GPU) string { return strings.TrimSpace(g.Vendor + " " + g.Model) }
