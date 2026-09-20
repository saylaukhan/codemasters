//go:build !windows

package update

// verifySignature passes outside Windows: the release of the agent is an MSI
// signed with an Authenticode certificate (installer/wix, plan.md §4.6), and
// there is nothing to check such a signature with here. The agent is not
// updated by MSI outside Windows anyway — Install refuses it.
func verifySignature(string) error { return nil }
