package models

import "testing"

func TestClusters(t *testing.T) {
	c := NewClusters("nancy", []Cluster{{UID: "graffiti"}, {UID: "gros"}})
	var m Model = c
	if m.Len() != 2 || c.Site != "nancy" {
		t.Fatalf("Len=%d Site=%q", m.Len(), c.Site)
	}
	if c = c.Move(1); c.Cursor != 1 {
		t.Errorf("Move(1): Cursor = %d", c.Cursor)
	}
	if c = c.Move(1); c.Cursor != 1 {
		t.Errorf("Move past the end: Cursor = %d", c.Cursor)
	}
	if NewClusters("nancy", nil).Move(1).Cursor != 0 {
		t.Error("empty list: Cursor stays 0")
	}
}
