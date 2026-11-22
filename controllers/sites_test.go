package controllers

import (
	"errors"
	"strings"
	"testing"

	"grid-tui/models"
)

func TestLoadsTheSitesAtStart(t *testing.T) {
	c := sized(t, New(working))
	if v := c.View(); !strings.Contains(v, "loading") {
		t.Errorf("before the sites arrive it should say loading:\n%s", v)
	}
	c = run(t, c, c.Init())
	if c.Model().Len() != 2 {
		t.Fatalf("Len = %d, want 2", c.Model().Len())
	}
	v := c.View()
	for _, want := range []string{"sites: 2", "nancy", "Grid5000 Rennes site", "enter clusters"} {
		if !strings.Contains(v, want) {
			t.Errorf("view missing %q:\n%s", want, v)
		}
	}
}

func TestMoveSelectsASite(t *testing.T) {
	c := loaded(t)
	for _, step := range []struct {
		key  string
		want string
	}{{"down", "rennes"}, {"down", "rennes"}, {"k", "nancy"}, {"j", "rennes"}, {"up", "nancy"}} {
		c, _ = press(t, c, step.key)
		if site, _ := c.Model().(models.Sites).Selected(); site.UID != step.want {
			t.Errorf("after %s: %q, want %q", step.key, site.UID, step.want)
		}
	}
}

func TestSitesLoadErrorIsShownAndReloadRetries(t *testing.T) {
	var calls int32
	c := sized(t, New(fakeClient{err: errors.New("GET /sites: 401 Unauthorized"), calls: &calls}))
	c = run(t, c, c.Init())
	if v := c.View(); !strings.Contains(v, "401 Unauthorized") {
		t.Errorf("the error should be on screen:\n%s", v)
	}

	c.client = fakeClient{sites: twoSites, calls: &calls} // now it works
	c, cmd := press(t, c, "r")
	if !c.loading || c.err != nil {
		t.Errorf("r should start loading and clear the error")
	}
	c = run(t, c, cmd)
	if c.Model().Len() != 2 || c.err != nil || calls != 2 {
		t.Errorf("after reload: Len=%d err=%v calls=%d", c.Model().Len(), c.err, calls)
	}
}

func TestSitesErrorKeepsTheOldSites(t *testing.T) {
	next, _ := loaded(t).Update(SitesLoadedMsg{Err: errors.New("timeout")})
	if c := next.(Controller); c.Model().Len() != 2 {
		t.Errorf("a failed reload should keep the sites, Len=%d", c.Model().Len())
	}
}

func TestKeysWhileSitesLoadDoNothing(t *testing.T) {
	c := sized(t, New(working)) // loading since New
	for _, k := range []string{"r", "enter"} {
		if _, cmd := press(t, c, k); cmd != nil {
			t.Errorf("%s while loading should not start another load", k)
		}
	}
}
