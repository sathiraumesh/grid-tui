package models

// Hardware is what one node of a cluster is made of. The nodes of a
// cluster are normally all the same, so it describes the whole cluster.
type Hardware struct {
	CPU      string  // processor model, e.g. "Intel Xeon Gold 5220"
	Sockets  int     // CPUs per node
	Cores    int     // cores per node, all CPUs together
	Threads  int     // hardware threads per node
	ClockGHz float64 // base clock

	MemoryBytes int64 // RAM

	Disks []Disk
	NICs  []NIC // the network cards that are connected
	GPUs  []GPU
}

// Disk is one storage device of a node.
type Disk struct {
	Kind      string // "SSD" or "HDD"
	Interface string // e.g. "SATA", "NVME"
	Model     string
	Bytes     int64
}

// NIC is one network card of a node.
type NIC struct {
	Interface string // e.g. "Ethernet", "InfiniBand"
	RateBps   int64  // bits per second
}

// GPU is one graphics card of a node.
type GPU struct {
	Vendor      string
	Model       string
	MemoryBytes int64
}

// IsZero is whether nothing is known about the hardware (not loaded yet).
func (h Hardware) IsZero() bool {
	return h.CPU == "" && h.Cores == 0 && h.MemoryBytes == 0 && len(h.Disks) == 0 && len(h.NICs) == 0 && len(h.GPUs) == 0
}
