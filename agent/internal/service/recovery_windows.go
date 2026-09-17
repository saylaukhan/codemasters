//go:build windows

package service

import (
	"time"

	"golang.org/x/sys/windows/svc/mgr"
)

// windowsUserName runs the service as LocalService: minimal rights (plan.md §4.1).
const windowsUserName = `NT AUTHORITY\LocalService`

// setRecoveryActions restarts the service after a crash in 1 min, 1 min and
// 5 min (plan.md §4.1). kardianos/service can set only a single action.
// The failure counter resets after a day without crashes.
func setRecoveryActions(name string) error {
	m, err := mgr.Connect()
	if err != nil {
		return err
	}
	defer func() { _ = m.Disconnect() }()

	s, err := m.OpenService(name)
	if err != nil {
		return err
	}
	defer s.Close()

	return s.SetRecoveryActions([]mgr.RecoveryAction{
		{Type: mgr.ServiceRestart, Delay: time.Minute},
		{Type: mgr.ServiceRestart, Delay: time.Minute},
		{Type: mgr.ServiceRestart, Delay: 5 * time.Minute},
	}, uint32((24 * time.Hour).Seconds()))
}
