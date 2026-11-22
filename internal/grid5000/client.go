// Package grid5000 is the connection to the Grid'5000 REST API
// (https://api.grid5000.fr). It knows nothing about the UI: it returns the
// app's own data types from internal/models.
package grid5000

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

// DefaultBaseURL is the root of the stable API.
const DefaultBaseURL = "https://api.grid5000.fr/stable"

// Client calls the Grid'5000 API.
//
// On a Grid'5000 frontend no credentials are needed. From anywhere else
// the API wants HTTP basic auth with your Grid'5000 login.
type Client struct {
	BaseURL  string
	User     string
	Password string
	HTTP     *http.Client
}

// NewClient makes a client from the environment:
//
//	G5K_USER, G5K_PASSWORD   your Grid'5000 login (not needed on a frontend)
//	G5K_API                  the API root, default DefaultBaseURL
func NewClient() *Client {
	base := os.Getenv("G5K_API")
	if base == "" {
		base = DefaultBaseURL
	}
	return &Client{
		BaseURL:  strings.TrimRight(base, "/"),
		User:     os.Getenv("G5K_USER"),
		Password: os.Getenv("G5K_PASSWORD"),
		HTTP:     &http.Client{Timeout: 30 * time.Second},
	}
}

// Error is a response that isn't a success.
type Error struct {
	Path   string // e.g. "/sites"
	Status int    // the HTTP status code
}

func (e *Error) Error() string {
	msg := fmt.Sprintf("GET %s: %d %s", e.Path, e.Status, http.StatusText(e.Status))
	if e.Status == http.StatusUnauthorized {
		msg += " (outside Grid'5000, set G5K_USER and G5K_PASSWORD)"
	}
	return msg
}

// get calls GET BaseURL+path and decodes the JSON answer into v.
func (c *Client) get(ctx context.Context, path string, v any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.BaseURL+path, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	if c.User != "" {
		req.SetBasicAuth(c.User, c.Password)
	}

	hc := c.HTTP
	if hc == nil {
		hc = http.DefaultClient
	}
	resp, err := hc.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return &Error{Path: path, Status: resp.StatusCode}
	}
	if err := json.NewDecoder(resp.Body).Decode(v); err != nil {
		return fmt.Errorf("GET %s: reading the answer: %w", path, err)
	}
	return nil
}

// collection is how the API wraps a list: {"items": [...], "total": n, "offset": 0}.
type collection[T any] struct {
	Items  []T `json:"items"`
	Total  int `json:"total"`
	Offset int `json:"offset"`
}
