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
func (l listing) Lines() []string {
	out := make([]string, l.n)
	for i := range out {
		out[i] = fmt.Sprintf("line %d", i+1)
	}
	return out
}

func TestRenderFillsTheScreenExactly(t *testing.T) {
	for _, v := range []View{nil, listing{0}, listing{100}, SitesView{Sites: sampleSites()}} {
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
	if !strings.Contains(s, emptyText) || !strings.Contains(s, HelpText) || strings.Contains(s, "$ ") {
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
	if !strings.Contains(strings.Join(lines, "\n"), emptyText) {
		t.Errorf("no lines should show %q", emptyText)
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

func TestRenderBeforeResize(t *testing.T) {
	if Render(nil, Status{}, 0, 0) != "loading..." {
		t.Error("no size yet should show loading...")
	}
}

func TestFor(t *testing.T) {
	if _, ok := For(models.NewSites(nil)).(SitesView); !ok {
		t.Error("For(Sites) should be a SitesView")
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
		{Status{}, HelpText},
		{Status{Loading: true}, "loading…"},
		{Status{Err: errors.New("GET /sites: 401 Unauthorized")}, "error: GET /sites: 401 Unauthorized • r retry"},
		{Status{Loading: true, Err: errors.New("boom")}, "error: boom"}, // the error wins
	}
	for _, c := range cases {
		lines := strings.Split(Render(nil, c.status, 100, 24), "\n")
		if last := lines[len(lines)-1]; !strings.Contains(last, c.want) {
			t.Errorf("%+v: bottom line %q, want %q", c.status, last, c.want)
		}
		if len(lines) != 24 {
			t.Errorf("%+v: %d lines, want 24", c.status, len(lines))
		}
	}
}
