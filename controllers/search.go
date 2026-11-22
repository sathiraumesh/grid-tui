package controllers

import (
	"context"
	"errors"
	"sync"

	tea "github.com/charmbracelet/bubbletea"

	"grid-tui/models"
)

// The search: / on the sites opens a form of requirements, and the
// clusters of every site that meet them are listed under it.
//
// The first time, every site's clusters and their hardware load, one site
// at a time in parallel; each fills in the results when it arrives. They
// are kept for the next time; r loads them again.
//
//	/ ──▶ loadSiteIndex (one per site) ──▶ client.Clusters + client.ClusterHardware ──▶ SiteIndexedMsg
//
// Keys on the form:
//
//	↑↓            fields, then the results
//	enter, space  tick a flag · next option of a choice · open a result
//	←→            the choices (on a result: scroll sideways)
//	0-9 ⌫         type a minimum
//	esc           back to the sites

// SiteIndexedMsg is what loadSiteIndex sends for one site.
type SiteIndexedMsg struct {
	Site     string
	Clusters []models.Cluster // with their hardware (or HardwareFailed)
	Err      error
}

// loadSiteIndex loads a site's clusters, then the hardware of each at the
// same time, in the background.
func loadSiteIndex(c Client, site string) tea.Cmd {
	return func() tea.Msg {
		ctx := context.Background()
		clusters, err := c.Clusters(ctx, site)
		if err != nil {
			return SiteIndexedMsg{Site: site, Err: err}
		}
		var (
			wg   sync.WaitGroup
			mu   sync.Mutex
			errs []error
		)
		for i := range clusters {
			wg.Add(1)
			go func(cl *models.Cluster) {
				defer wg.Done()
				h, err := c.ClusterHardware(ctx, site, cl.UID)
				if err != nil {
					cl.HardwareState = models.HardwareFailed
					mu.Lock()
					errs = append(errs, err)
					mu.Unlock()
					return
				}
				cl.Hardware, cl.HardwareState = h, models.HardwareLoaded
			}(&clusters[i])
		}
		wg.Wait()
		return SiteIndexedMsg{Site: site, Clusters: clusters, Err: errors.Join(errs...)}
	}
}

// openSearch shows the search, and loads every site the first time.
func (c Controller) openSearch() (tea.Model, tea.Cmd) {
	if c.client == nil || c.sites.Len() == 0 {
		return c, nil
	}
	var cmd tea.Cmd
	if c.search.SitesTotal == 0 {
		c.search = models.NewSearch(c.sites.Len())
		cmd = c.indexSites()
	}
	c.model = c.search
	c.err = nil
	return c, cmd
}

// indexSites starts loading every site for the search.
func (c Controller) indexSites() tea.Cmd {
	loads := make([]tea.Cmd, 0, c.sites.Len())
	for _, s := range c.sites.Items {
		loads = append(loads, loadSiteIndex(c.client, s.UID))
	}
	return tea.Batch(loads...)
}

// onSiteIndexed adds a site's clusters to the search. It is kept while a
// result's detail is shown, so esc finds it there.
func (c Controller) onSiteIndexed(msg SiteIndexedMsg) Controller {
	c.search = c.search.WithSite(msg.Site, msg.Clusters)
	if _, onSearch := c.model.(models.Search); onSearch {
		c.model = c.search
		if msg.Err != nil {
			c.err = errors.Join(c.err, msg.Err)
		}
	}
	return c
}

// reloadSearch loads every site again, keeping the requirements.
func (c Controller) reloadSearch() (tea.Model, tea.Cmd) {
	if c.client == nil || c.search.Loading() {
		return c, nil
	}
	c.search.SitesTotal, c.search.SitesDone = c.sites.Len(), 0
	c.model, c.err = c.search, nil
	return c, c.indexSites()
}

// onSearchKey is what keys do on the search.
func (c Controller) onSearchKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	s := c.search
	field, onField := s.FocusedField()
	kind := models.FieldKind(-1)
	if onField {
		kind = models.SearchFields[field].Kind
	}

	switch key := msg.String(); {
	case key == keyQuit || key == keyCtrlC:
		return c, tea.Quit
	case key == keyBack:
		return c.back(), nil
	case key == keyBackAlt: // backspace: a digit on a number, else back
		if kind == models.FieldNumber {
			s = s.Backspace()
		} else {
			return c.back(), nil
		}
	case key == keyUp || key == keyUpAlt:
		s = s.Move(-1)
	case key == keyDown || key == keyDownAlt:
		s = s.Move(1)
	case key == keyLeft || key == keyLeftAlt, key == keyRight || key == keyRightAlt:
		step := 1
		if key == keyLeft || key == keyLeftAlt {
			step = -1
		}
		if !onField {
			return c.scroll(step * scrollStep), nil
		}
		s = s.Cycle(step)
	case key == keyOpen || key == keyToggle:
		switch kind {
		case models.FieldFlag:
			s = s.Toggle()
		case models.FieldChoice:
			s = s.Cycle(1)
		case models.FieldNumber:
			s = s.Move(1) // done with this number: on to the next field
		default:
			return c.openResult()
		}
	case key == keyReload:
		return c.reloadSearch()
	case len(msg.Runes) == 1 && msg.Runes[0] >= '0' && msg.Runes[0] <= '9':
		s = s.Type(msg.Runes[0])
	default:
		return c, nil
	}
	c.search, c.model = s, s
	return c, nil
}

// openResult shows the detail of the selected result and starts loading
// it; esc there comes back to the search.
func (c Controller) openResult() (tea.Model, tea.Cmd) {
	e, ok := c.search.Selected()
	if !ok || c.client == nil {
		return c, nil
	}
	c.returnTo = c.search
	c.model = models.NewClusterDetail(e.Site, e.Cluster)
	c.loading, c.err, c.scrollX = true, nil, 0
	return c, loadDetail(c.client, e.Site, e.Cluster.UID)
}
