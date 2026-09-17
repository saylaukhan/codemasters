package netinfo

import (
	"context"
	"net"
	"slices"
	"strings"
	"time"
)

// WatchInterval is how often Watch looks at the adapters. The OS notifications
// of a network change differ between Windows and Linux; polling is the same
// everywhere and needs no extra dependency (T-13).
const WatchInterval = 15 * time.Second

// Addrs is a snapshot of the adapters that are up and their IP addresses,
// adapter name -> sorted addresses.
type Addrs map[string][]string

// Snapshot describes the adapters that are up now. The loopback and
// link-local addresses are left out: they do not tell the network apart.
func Snapshot() (Addrs, error) {
	ifaces, err := net.Interfaces()
	if err != nil {
		return nil, err
	}
	cur := make(Addrs, len(ifaces))
	for _, iface := range ifaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
			continue
		}
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		list := []string{}
		for _, addr := range addrs {
			ipnet, ok := addr.(*net.IPNet)
			if !ok || ipnet.IP.IsLinkLocalUnicast() || ipnet.IP.IsLinkLocalMulticast() {
				continue
			}
			list = append(list, ipnet.IP.String())
		}
		slices.Sort(list)
		cur[iface.Name] = list
	}
	return cur, nil
}

// Changes describes what differs between two snapshots for the log, or "" when
// the network is the same: a new adapter as "+имя", a gone one as "-имя", a
// changed address list as "имя: старое → новое".
func Changes(old, cur Addrs) string {
	names := make([]string, 0, len(old)+len(cur))
	for name := range old {
		names = append(names, name)
	}
	for name := range cur {
		if _, ok := old[name]; !ok {
			names = append(names, name)
		}
	}
	slices.Sort(names)

	var parts []string
	for _, name := range names {
		before, had := old[name]
		after, has := cur[name]
		switch {
		case !has:
			parts = append(parts, "-"+name)
		case !had:
			parts = append(parts, "+"+name+" "+strings.Join(after, ","))
		case !slices.Equal(before, after):
			parts = append(parts, name+": "+strings.Join(before, ",")+" → "+strings.Join(after, ","))
		}
	}
	return strings.Join(parts, "; ")
}

// Watch calls onChange with a description of the change every time the set of
// adapters or their addresses changes, until ctx is done. A computer moved to
// another line or another Wi-Fi network is noticed without a restart of the
// service (ТЗ п. 2, plan.md §4.2). onChange runs in the goroutine of Watch:
// while it works, changes are not looked for.
func Watch(ctx context.Context, interval time.Duration, onChange func(change string)) {
	if interval <= 0 {
		interval = WatchInterval
	}
	prev, err := Snapshot()
	if err != nil {
		prev = Addrs{}
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
		cur, err := Snapshot()
		if err != nil {
			continue
		}
		if change := Changes(prev, cur); change != "" {
			prev = cur
			onChange(change)
		}
	}
}
