package netinfo

import "testing"

func TestChanges(t *testing.T) {
	base := Addrs{"eth0": {"192.168.1.10"}, "wlan0": {"10.0.0.5"}}
	cases := map[string]struct {
		cur  Addrs
		want string
	}{
		"same network":    {Addrs{"eth0": {"192.168.1.10"}, "wlan0": {"10.0.0.5"}}, ""},
		"new address":     {Addrs{"eth0": {"192.168.2.10"}, "wlan0": {"10.0.0.5"}}, "eth0: 192.168.1.10 → 192.168.2.10"},
		"adapter is down": {Addrs{"wlan0": {"10.0.0.5"}}, "-eth0"},
		"adapter is up": {Addrs{"eth0": {"192.168.1.10"}, "usb0": {"172.16.0.2"}, "wlan0": {"10.0.0.5"}},
			"+usb0 172.16.0.2"},
		"cable instead of wi-fi": {Addrs{"eth0": {"192.168.1.10"}}, "-wlan0"},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			if got := Changes(base, tc.cur); got != tc.want {
				t.Fatalf("Changes = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestSnapshotRuns(t *testing.T) {
	cur, err := Snapshot()
	if err != nil {
		t.Fatalf("Snapshot: %v", err)
	}
	if Changes(cur, cur) != "" {
		t.Fatalf("Changes of one snapshot with itself = %q, want no change", Changes(cur, cur))
	}
}
