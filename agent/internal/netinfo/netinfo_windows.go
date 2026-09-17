package netinfo

import (
	"errors"
	"fmt"
	"net"
	"unsafe"

	"golang.org/x/sys/windows"
)

func describe(ip net.IP) (Info, error) {
	size := uint32(15 << 10)
	var buf []byte
	for {
		buf = make([]byte, size)
		err := windows.GetAdaptersAddresses(windows.AF_UNSPEC, windows.GAA_FLAG_INCLUDE_GATEWAYS, 0,
			(*windows.IpAdapterAddresses)(unsafe.Pointer(&buf[0])), &size)
		if err == nil {
			break
		}
		if !errors.Is(err, windows.ERROR_BUFFER_OVERFLOW) {
			return Info{Type: Other}, fmt.Errorf("GetAdaptersAddresses: %w", err)
		}
	}

	for aa := (*windows.IpAdapterAddresses)(unsafe.Pointer(&buf[0])); aa != nil; aa = aa.Next {
		for ua := aa.FirstUnicastAddress; ua != nil; ua = ua.Next {
			if !ua.Address.IP().Equal(ip) {
				continue
			}
			info := Info{Interface: windows.UTF16PtrToString(aa.FriendlyName), Type: Other}
			switch aa.IfType {
			case windows.IF_TYPE_ETHERNET_CSMACD:
				info.Type = Ethernet
			case windows.IF_TYPE_IEEE80211:
				info.Type = WiFi
			}
			for gw := aa.FirstGatewayAddress; gw != nil; gw = gw.Next {
				if g := gw.Address.IP(); g != nil && (g.To4() != nil) == (ip.To4() != nil) {
					info.Gateway = g.String()
					break
				}
			}
			return info, nil
		}
	}
	return Info{Type: Other}, fmt.Errorf("нет адаптера с адресом %s", ip)
}
