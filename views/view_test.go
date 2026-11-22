package views

import (
	"errors"
	"fmt"
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"

	"grid-tui/models"
)

// listing is a test view with labels, a command and n lines, to check
// Render draws any View.
type listing struct{ n int }

func (l listing) Labels() []string { return []string{"one", "two"} }
func (l listing) Command() string  { return "curl https://example.test/list" }
func (l listing) Help() string     { return "listing help" }
func (l listing) Lines() []string {
	out := make([]string, l.n)
	for i := range out {
		out[i] = fmt.Sprintf("line %d", i+1)
	}
	return out
}

// picked is a listing with line sel selected.
type picked struct {
	listing
	sel int
}

func (p picked) Selected() int { return p.sel }

func TestRenderFillsTheScreenExactly(t *testing.T) {
	views := []View{nil, listing{0}, listing{100}, picked{listing{100}, 80},
		SitesView{Sites: sampleSites()}, ClustersView{Clusters: sampleClusters()}}
	for _, v := range views {
		for _, size := range [][2]int{{100, 24}, {80, 40}, {60, 10}} {
			lines := strings.Split(Render(v, Status{}, size[0], size[1]), "\n")
			if len(lines) != size[1] {
				t.Errorf("%T %dx%d: %d lines, want %d", v, size[0], size[1], len(lines), size[1])
			}
			for i, l := range lines {
				if w := lipgloss.Width(l); w > size[0] {
					t.Errorf("%T %dx%d: line %d is %d wide", v, size[0], size[1], i, w)
				}
			}
		}
	}
}

func TestRenderNil(t *testing.T) {
	s := Render(nil, Status{}, 100, 24)
	if !strings.Contains(s, emptyText) || !strings.Contains(s, defaultHelp) || strings.Contains(s, "$ ") {
		t.Errorf("nil view should be an empty panel with no command:\n%s", s)
	}
}

func TestRenderBorders(t *testing.T) {
	lines := strings.Split(Render(listing{0}, Status{}, 100, 24), "\n")
	top, bottom := lines[panelMarginY], lines[len(lines)-1-panelMarginY-1]
	if !strings.Contains(top, "one") || !strings.Contains(top, "two") {
		t.Errorf("top border missing labels: %s", top)
	}
	if !strings.Contains(bottom, "$ curl https://example.test/list") {
		t.Errorf("bottom border missing command: %s", bottom)
	}
	if s := strings.Join(lines, "\n"); !strings.Contains(s, emptyText) || !strings.Contains(s, "listing help") {
		t.Errorf("want %q and the view's help:\n%s", emptyText, s)
	}
}

func TestRenderCutsLinesToFit(t *testing.T) {
	s := Render(listing{100}, Status{}, 100, 24)
	h := ContentHeight(24)
	last, next := fmt.Sprintf("line %d ", h), fmt.Sprintf("line %d ", h+1)
	if !strings.Contains(s, "line 1 ") || !strings.Contains(s, last) || strings.Contains(s, next) {
		t.Errorf("should show the first %d lines:\n%s", h, s)
	}
}

func TestRenderScrollsToTheSelectedLine(t *testing.T) {
	h := ContentHeight(24)
	s := Render(picked{listing{100}, 49}, Status{}, 100, 24) // "line 50"
	first, last := fmt.Sprintf("line %d ", 50-h+1), "line 50 "
	if !strings.Contains(s, first) || !strings.Contains(s, last) || strings.Contains(s, "line 51 ") || strings.Contains(s, "line 1 ") {
		t.Errorf("should show lines %d-50:\n%s", 50-h+1, s)
	}
}

func TestWindow(t *testing.T) {
	lines := []string{"a", "b", "c", "d", "e"}
	cases := []struct {
		sel, h  int
		want    string
		wantSel int
	}{
		{-1, 3, "abc", -1},
		{1, 3, "abc", 1},
		{4, 3, "cde", 2},
		{2, 10, "abcde", 2},
	}
	for _, c := range cases {
		got, sel := window(lines, c.sel, c.h)
		if strings.Join(got, "") != c.want || sel != c.wantSel {
			t.Errorf("window(sel=%d, h=%d) = %q, %d; want %q, %d", c.sel, c.h, got, sel, c.want, c.wantSel)
		}
	}
}

func TestRenderBeforeResize(t *testing.T) {
	if Render(nil, Status{}, 0, 0) != "loading..." {
		t.Error("no size yet should show loading...")
	}
}

func TestFor(t *testing.T) {
	if _, ok := For(models.NewSites(nil)).(SitesView); !ok {
		t.Error("For(Sites) should be a SitesView")
	}
	if _, ok := For(models.NewClusters("nancy", nil)).(ClustersView); !ok {
		t.Error("For(Clusters) should be a ClustersView")
	}
	if For(nil) != nil {
		t.Error("For(nil) should be nil")
	}
}

func TestBottomLine(t *testing.T) {
	cases := []struct {
		status Status
		want   string
	}{
		{Status{}, "listing help"},
		{Status{Loading: true}, "loading…"},
		{Status{Err: errors.New("GET /sites: 401 Unauthorized")}, "error: GET /sites: 401 Unauthorized • r retry • listing help"},
		{Status{Loading: true, Err: errors.New("boom")}, "error: boom"}, // the error wins
	}
	for _, c := range cases {
		lines := strings.Split(Render(listing{0}, c.status, 100, 24), "\n")
		if last := lines[len(lines)-1]; !strings.Contains(last, c.want) {
			t.Errorf("%+v: bottom line %q, want %q", c.status, last, c.want)
		}
		if len(lines) != 24 {
			t.Errorf("%+v: %d lines, want 24", c.status, len(lines))
		}
	}
}
