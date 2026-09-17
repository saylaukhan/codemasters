package netinfo

import (
	"net"
	"os"
	"path/filepath"
	"strings"
)

func describe(ip net.IP) (Info, error) {
	iface, err := interfaceByIP(ip)
	if err != nil {
		return Info{Type: Other}, err
	}
	info := Info{Interface: iface.Name, Type: Other}
	dir := filepath.Join("/sys/class/net", iface.Name)
	switch {
	case exists(filepath.Join(dir, "wireless")) || exists(filepath.Join(dir, "phy80211")):
		info.Type = WiFi
	// ARPHRD_ETHER with a hardware device; bridges, veth and tunnels have no device.
	case readTrim(filepath.Join(dir, "type")) == "1" && exists(filepath.Join(dir, "device")):
		info.Type = Ethernet
	}
	if routes, err := os.ReadFile("/proc/net/route"); err == nil {
		info.Gateway = defaultGateway(routes, iface.Name)
	}
	return info, nil
}

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func readTrim(path string) string {
	data, _ := os.ReadFile(path)
	return strings.TrimSpace(string(data))
}
