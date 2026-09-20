//go:build !windows

package update

import (
	"os/exec"
	"syscall"
)

// detach puts the updater into a session of its own, so stopping the unit
// does not take it down together with the agent. The release itself is a
// Windows MSI (installer/wix); outside Windows this path exists so the
// package builds and its tests run on the developer machines (`make check`).
func detach(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
}
