package models

import "testing"

var three = []Site{{UID: "lyon"}, {UID: "nancy"}, {UID: "rennes"}}

func TestSites(t *testing.T) {
	var m Model = NewSites(three)
	if m.Len() != 3 {
		t.Errorf("Len = %d, want 3", m.Len())
	}
	if NewSites(nil).Len() != 0 {
		t.Error("no sites should have Len 0")
	}
}

func TestSitesMoveAndSelected(t *testing.T) {
	s := NewSites(three)
	cases := []struct {
		step int
		want string
	}{
		{0, "lyon"}, {1, "nancy"}, {1, "rennes"}, {1, "rennes"}, {-5, "lyon"},
	}
	for _, c := range cases {
		s = s.Move(c.step)
		if got, ok := s.Selected(); !ok || got.UID != c.want {
			t.Errorf("after Move(%d): %q, want %q", c.step, got.UID, c.want)
		}
	}
	if _, ok := NewSites(nil).Move(1).Selected(); ok {
		t.Error("no sites: nothing selected")
	}
}

func TestSitesWithItemsKeepsTheCursorInside(t *testing.T) {
	s := NewSites(three).Move(2).WithItems(three[:1])
	if s.Cursor != 0 {
		t.Errorf("Cursor = %d, want 0 after the list shrank", s.Cursor)
	}
}
