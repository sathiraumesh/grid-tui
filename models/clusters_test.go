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

func TestWattmeter(t *testing.T) {
	with := Cluster{Metrics: []Metric{{Name: "bmc_node_power_watt"}, {Name: "wattmetre_power_watt"}}}
	without := Cluster{Metrics: []Metric{{Name: "bmc_node_power_watt"}}}
	if !with.Wattmeter() || without.Wattmeter() || (Cluster{}).Wattmeter() {
		t.Error("Wattmeter should be true only with a wattmetre_* metric")
	}
}

func TestWithHardware(t *testing.T) {
	c := NewClusters("nancy", []Cluster{{UID: "graffiti"}, {UID: "gros"}})
	d := c.WithHardware("gros", Hardware{Nodes: 124, Cores: 18}, true).WithHardware("graffiti", Hardware{Cores: 1}, false)
	if g := d.Items[1]; g.HardwareState != HardwareLoaded || g.Hardware.Nodes != 124 {
		t.Errorf("gros = %+v", g)
	}
	if g := d.Items[0]; g.HardwareState != HardwareFailed || !g.Hardware.IsZero() {
		t.Errorf("graffiti = %+v", g)
	}
	if c.Items[1].HardwareState != HardwareLoading {
		t.Error("the original model should not change")
	}
}
