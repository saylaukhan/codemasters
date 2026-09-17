// Package netinfo describes the network a measurement goes through: the
// active adapter, its type and the default gateway (plan.md §4.3, step 2).
// A Wi‑Fi measurement is flagged and left out of the line status (ТЗ п. 10,
// ADR-012).
package netinfo

import (
	"fmt"
	"net"
	"strconv"
	"strings"
)

// IfaceType is iface_type of a measurement.
type IfaceType string

const (
	Ethernet IfaceType = "ethernet"
	WiFi     IfaceType = "wifi"
	Other    IfaceType = "other"
)

// Info is the adapter the traffic to the measurement server leaves through.
type Info struct {
	Interface string
	Type      IfaceType
	LocalIP   string
	// Gateway is the default gateway of the adapter; empty when unknown.
	Gateway string
}

// Detect finds the adapter the OS routes traffic to host through. Type is
// Other and Gateway is empty where the OS does not tell them.
func Detect(host string) (Info, error) {
	// A UDP "connection" only selects the route: no packet is sent.
	conn, err := net.Dial("udp", net.JoinHostPort(host, "80"))
	if err != nil {
		return Info{Type: Other}, fmt.Errorf("маршрут до %s: %w", host, err)
	}
	local := conn.LocalAddr().(*net.UDPAddr).IP
	_ = conn.Close()

	info, err := describe(local)
	info.LocalIP = local.String()
	return info, err
}

// interfaceByIP returns the interface that has ip among its addresses.
func interfaceByIP(ip net.IP) (net.Interface, error) {
	ifaces, err := net.Interfaces()
	if err != nil {
		return net.Interface{}, err
	}
	for _, iface := range ifaces {
		addrs, err := iface.Addrs()
		if err != nil {
			continue
		}
		for _, addr := range addrs {
			if ipnet, ok := addr.(*net.IPNet); ok && ipnet.IP.Equal(ip) {
				return iface, nil
			}
		}
	}
	return net.Interface{}, fmt.Errorf("нет адаптера с адресом %s", ip)
}

// defaultGateway returns the IPv4 default gateway of iface from the contents
// of /proc/net/route (Linux), or "" if there is none.
func defaultGateway(procRoute []byte, iface string) string {
	for _, line := range strings.Split(string(procRoute), "\n") {
		f := strings.Fields(line)
		if len(f) < 3 || f[0] != iface || f[1] != "00000000" {
			continue
		}
		gw, err := strconv.ParseUint(f[2], 16, 32)
		if err != nil || gw == 0 {
			continue
		}
		// The kernel prints the address in host byte order: little-endian on x86 and ARM.
		return net.IPv4(byte(gw), byte(gw>>8), byte(gw>>16), byte(gw>>24)).String()
	}
	return ""
}
