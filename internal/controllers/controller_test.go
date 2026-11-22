package controllers

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/internal/models"
)

// started is a controller on a 100×24 terminal.
func started(t *testing.T) Controller {
	t.Helper()
	next, _ := New(models.NewSites(nil)).Update(tea.WindowSizeMsg{Width: 100, Height: 24})
	return next.(Controller)
}

func TestResizeStoresTheSize(t *testing.T) {
	if w, h := started(t).Size(); w != 100 || h != 24 {
		t.Errorf("size = %dx%d, want 100x24", w, h)
	}
}

func TestViewShowsTheModel(t *testing.T) {
	if v := started(t).View(); !strings.Contains(v, "sites: 0") {
		t.Errorf("View should draw the model:\n%s", v)
	}
}

func TestQuit(t *testing.T) {
	for _, k := range []tea.KeyMsg{
		{Type: tea.KeyRunes, Runes: []rune("q")},
		{Type: tea.KeyCtrlC},
	} {
		_, cmd := started(t).Update(k)
		if cmd == nil {
			t.Fatalf("%s should quit", k)
		}
		if _, ok := cmd().(tea.QuitMsg); !ok {
			t.Fatalf("%s should return tea.Quit", k)
		}
	}
}

func TestOtherKeysDoNothing(t *testing.T) {
	before := started(t)
	next, cmd := before.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("x")})
	after := next.(Controller)
	if cmd != nil || after.View() != before.View() || after.Model().Len() != before.Model().Len() {
		t.Error("x should change nothing")
	}
}
