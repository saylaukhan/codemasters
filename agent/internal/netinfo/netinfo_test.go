package netinfo

import "testing"

func TestDefaultGateway(t *testing.T) {
	routes := []byte(`Iface	Destination	Gateway 	Flags	RefCnt	Use	Metric	Mask		MTU	Window	IRTT
eth0	0000A8C0	00000000	0001	0	0	100	00FFFFFF	0	0	0
wlan0	00000000	0101A8C0	0003	0	0	600	00000000	0	0	0
eth0	00000000	FE01A8C0	0003	0	0	100	00000000	0	0	0
`)
	for iface, want := range map[string]string{"eth0": "192.168.1.254", "wlan0": "192.168.1.1", "lo": ""} {
		if got := defaultGateway(routes, iface); got != want {
			t.Errorf("defaultGateway(%s) = %q, want %q", iface, got, want)
		}
	}
}

func TestDetectLoopback(t *testing.T) {
	info, err := Detect("127.0.0.1")
	if err != nil {
		t.Fatalf("Detect: %v", err)
	}
	if info.LocalIP != "127.0.0.1" || info.Interface == "" || info.Type == "" {
		t.Fatalf("Detect = %+v, want the loopback adapter", info)
	}
}
