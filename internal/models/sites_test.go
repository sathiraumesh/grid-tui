package models

import "testing"

func TestSites(t *testing.T) {
	var m Model = NewSites([]Site{{UID: "nancy"}, {UID: "rennes"}})
	if m.Len() != 2 {
		t.Errorf("Len = %d, want 2", m.Len())
	}
	if NewSites(nil).Len() != 0 {
		t.Error("no sites should have Len 0")
	}
}
