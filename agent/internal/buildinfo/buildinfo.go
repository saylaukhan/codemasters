// Package buildinfo holds values injected into the binary at build time.
package buildinfo

// Version is the agent version shown by `vko-agent version`.
//
// Local builds report "dev". Release builds (agent-msi.yml) override it with:
//
//	-ldflags "-X github.com/saylaukhan/codemasters/agent/internal/buildinfo.Version=<tag>"
var Version = "dev"
