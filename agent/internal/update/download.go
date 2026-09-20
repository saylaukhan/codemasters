package update

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
)

// downloadTimeout bounds one download of a release. The API client has 30 s
// (api.requestTimeout) — that is for small JSON calls; an MSI of tens of
// megabytes over a school line needs far longer, so the download goes through
// a client of its own.
const downloadTimeout = 30 * time.Minute

// maxMSISize refuses what cannot be an agent installer: a wrong address or a
// captive portal must not fill the disk of a school computer.
const maxMSISize = 200 << 20

// updatesDirName is the folder inside DataDir with the downloaded releases
// and the file the current version was installed from.
const updatesDirName = "updates"

// UpdatesDir returns that folder inside dataDir.
func UpdatesDir(dataDir string) string {
	return filepath.Join(dataDir, updatesDirName)
}

// download streams the release to DataDir/updates/<version>.msi through a
// .part file: an interrupted download never looks like a file ready to
// install. The name is safe — the version is installed only when it reads as
// major.minor.patch (Newer), so it carries no path separators.
func download(ctx context.Context, o Options, rel api.Release) (string, error) {
	src, ours, err := resolveURL(o.ServerURL, rel.DownloadURL)
	if err != nil {
		return "", err
	}
	dir := UpdatesDir(o.DataDir)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", fmt.Errorf("папка обновлений %s: %w", dir, err)
	}
	path := filepath.Join(dir, rel.Version+".msi")
	part := path + ".part"

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, src, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "vko-agent/"+o.Version)
	// The device token goes to the monitoring server only: a release put on a
	// mirror or a CDN must not see it (ADR-005).
	if ours {
		if token := o.Client.Token(); token != "" {
			req.Header.Set("Authorization", "Device "+token)
		}
	}
	resp, err := (&http.Client{Timeout: downloadTimeout}).Do(req)
	if err != nil {
		return "", fmt.Errorf("скачивание %s: %w", src, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return "", fmt.Errorf("скачивание %s: сервер ответил %d", src, resp.StatusCode)
	}

	n, err := writeFile(part, io.LimitReader(resp.Body, maxMSISize+1))
	switch {
	case err != nil:
		remove(part)
		return "", fmt.Errorf("скачивание %s: %w", src, err)
	case n > maxMSISize:
		remove(part)
		return "", fmt.Errorf("скачивание %s: файл больше %d МБ, установка отменена", src, maxMSISize>>20)
	}
	if err := os.Rename(part, path); err != nil {
		remove(part)
		return "", err
	}
	o.Logger.Info("релиз скачан", "version", rel.Version, "path", path, "bytes", n)
	return path, nil
}

// writeFile writes r to path, replacing what is there, and returns the number
// of bytes written.
func writeFile(path string, r io.Reader) (int64, error) {
	f, err := os.OpenFile(path, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o644)
	if err != nil {
		return 0, err
	}
	n, err := io.Copy(f, r)
	if closeErr := f.Close(); err == nil {
		err = closeErr
	}
	return n, err
}

// remove deletes a file that must not stay; a failure is not worth an error
// of its own — the next download replaces the file anyway.
func remove(path string) {
	_ = os.Remove(path)
}

// resolveURL turns download_url of the release into an absolute address and
// reports whether it points at the monitoring server itself.
func resolveURL(serverURL, raw string) (src string, ours bool, err error) {
	base, err := url.Parse(serverURL)
	if err != nil {
		return "", false, fmt.Errorf("адрес сервера %q: %w", serverURL, err)
	}
	u, err := url.Parse(raw)
	if err != nil {
		return "", false, fmt.Errorf("адрес релиза %q: %w", raw, err)
	}
	abs := base.ResolveReference(u)
	if (abs.Scheme != "http" && abs.Scheme != "https") || abs.Host == "" {
		return "", false, fmt.Errorf("адрес релиза %q должен быть адресом http(s)://хост", raw)
	}
	return abs.String(), abs.Scheme == base.Scheme && abs.Host == base.Host, nil
}
