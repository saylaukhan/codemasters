package update

import (
	"strconv"
	"strings"
)

// DevVersion is what buildinfo.Version says in a local build. Such a binary is
// never replaced by a release: a developer machine must keep the code it was
// built from (T-50).
const DevVersion = "dev"

// Newer reports whether latest is a later version than current. A version is
// major.minor.patch ("0.2.0"); a missing part counts as zero and a leading "v"
// is allowed. A version that does not read like that — "dev" of a local build,
// a tag with a suffix — is never newer and is never updated over.
func Newer(current, latest string) bool {
	c, ok := parseVersion(current)
	if !ok {
		return false
	}
	l, ok := parseVersion(latest)
	if !ok {
		return false
	}
	for i := range c {
		if l[i] != c[i] {
			return l[i] > c[i]
		}
	}
	return false
}

// parseVersion reads major.minor.patch into three numbers; ok is false when
// the string is not that.
func parseVersion(v string) (parts [3]int, ok bool) {
	fields := strings.Split(strings.TrimPrefix(strings.TrimSpace(v), "v"), ".")
	if len(fields) > len(parts) {
		return [3]int{}, false
	}
	for i, f := range fields {
		n, err := strconv.Atoi(f)
		if err != nil || n < 0 {
			return [3]int{}, false
		}
		parts[i] = n
	}
	return parts, true
}
