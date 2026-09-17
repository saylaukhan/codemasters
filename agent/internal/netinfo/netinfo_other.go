//go:build !linux && !windows

package netinfo

import "net"

// describe outside Windows and Linux (a developer's macOS) knows only the
// adapter name.
func describe(ip net.IP) (Info, error) {
	iface, err := interfaceByIP(ip)
	return Info{Interface: iface.Name, Type: Other}, err
}
