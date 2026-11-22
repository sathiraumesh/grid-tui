// Package models holds the app's data. It knows nothing about drawing or
// keys: how a model looks is its view's job (the views package).
//
// Model is an interface so the app can hold different kinds of data: each
// kind (sites, clusters, nodes, jobs, …) is its own type implementing it.
package models

// Model is a kind of data the app shows.
type Model interface {
	// Len is how many items (rows) the model holds.
	Len() int
}

// moveCursor moves cursor by step in a list of n items, stopping at the
// first and last item (0 when the list is empty).
func moveCursor(cursor, step, n int) int {
	return max(min(cursor+step, n-1), 0)
}
