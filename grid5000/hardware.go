package grid5000

import (
	"context"
	"errors"
	"net/url"
	"sort"

	"grid-tui/models"
)

// The hardware of a cluster comes from the reference API's description of
// its nodes (abridged):
//
//	GET /sites/nancy/clusters/gros/nodes
//	{"items": [{
//	  "uid": "gros-1",
//	  "processor":    {"model": "Intel Xeon", "other_description": "Intel Xeon Gold 5220", "clock_speed": 2200000000},
//	  "architecture": {"nb_procs": 1, "nb_cores": 18, "nb_threads": 36},
//	  "main_memory":  {"ram_size": 103079215104},
//	  "storage_devices":  [{"storage": "SSD", "interface": "SATA", "model": "…", "size": 480103981056}],
//	  "network_adapters": [{"interface": "Ethernet", "rate": 25000000000, "mounted": true}],
//	  "gpu_devices": {"0": {"vendor": "Nvidia", "model": "A100", "memory": 42949672960}}}]}
//
// Sizes are bytes, the clock is Hz, network rates are bits per second.

// NodesPath is the API path of the node descriptions of a cluster.
func NodesPath(site, cluster string) string {
	return ClustersPath(site) + "/" + url.PathEscape(cluster) + "/nodes"
}

type nodeDescription struct {
	UID       string `json:"uid"`
	Processor struct {
		Model            string `json:"model"`
		OtherDescription string `json:"other_description"`
		ClockSpeed       number `json:"clock_speed"`
	} `json:"processor"`
	Architecture struct {
		Procs   number `json:"nb_procs"`
		Cores   number `json:"nb_cores"`
		Threads number `json:"nb_threads"`
	} `json:"architecture"`
	MainMemory struct {
		RAMSize number `json:"ram_size"`
	} `json:"main_memory"`
	StorageDevices []struct {
		Storage   string `json:"storage"`
		Interface string `json:"interface"`
		Model     string `json:"model"`
		Size      number `json:"size"`
	} `json:"storage_devices"`
	NetworkAdapters []struct {
		Interface string `json:"interface"`
		Rate      number `json:"rate"`
		Mounted   bool   `json:"mounted"`
	} `json:"network_adapters"`
	GPUDevices map[string]struct {
		Vendor string `json:"vendor"`
		Model  string `json:"model"`
		Memory number `json:"memory"`
	} `json:"gpu_devices"`
}

// ClusterHardware describes the hardware of a cluster, from its first node,
// and counts its nodes:
// GET /stable/sites/{site}/clusters/{cluster}/nodes.
func (c *Client) ClusterHardware(ctx context.Context, site, cluster string) (models.Hardware, error) {
	if site == "" || cluster == "" {
		return models.Hardware{}, errors.New("cluster hardware: site and cluster are needed")
	}
	var col collection[nodeDescription]
	if err := c.get(ctx, NodesPath(site, cluster), &col); err != nil {
		return models.Hardware{}, err
	}
	if len(col.Items) == 0 {
		return models.Hardware{}, errors.New("cluster hardware: " + cluster + " has no nodes")
	}
	h := hardwareOf(col.Items[0])
	h.Nodes = len(col.Items)
	return h, nil
}

func hardwareOf(n nodeDescription) models.Hardware {
	cpu := n.Processor.OtherDescription // the full name, e.g. "Intel Xeon Gold 5220"
	if cpu == "" {
		cpu = n.Processor.Model
	}
	h := models.Hardware{
		CPU:         cpu,
		Sockets:     int(n.Architecture.Procs),
		Cores:       int(n.Architecture.Cores),
		Threads:     int(n.Architecture.Threads),
		ClockGHz:    float64(n.Processor.ClockSpeed) / 1e9,
		MemoryBytes: int64(n.MainMemory.RAMSize),
	}
	for _, d := range n.StorageDevices {
		h.Disks = append(h.Disks, models.Disk{Kind: d.Storage, Interface: d.Interface, Model: d.Model, Bytes: int64(d.Size)})
	}
	for _, a := range n.NetworkAdapters {
		if a.Mounted { // only the cards that are connected
			h.NICs = append(h.NICs, models.NIC{Interface: a.Interface, RateBps: int64(a.Rate)})
		}
	}
	ids := make([]string, 0, len(n.GPUDevices))
	for id := range n.GPUDevices {
		ids = append(ids, id)
	}
	sort.Strings(ids) // a map has no order: keep the GPUs in a stable one
	for _, id := range ids {
		g := n.GPUDevices[id]
		h.GPUs = append(h.GPUs, models.GPU{Vendor: g.Vendor, Model: g.Model, MemoryBytes: int64(g.Memory)})
	}
	return h
}
