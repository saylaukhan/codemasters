package update

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/api"
)

// almaty is the local offset of a school computer (ADR-014).
var almaty = time.FixedZone("Asia/Almaty", 5*60*60)

// msiBody stands for the installer: the tests care about its hash, not its
// contents.
var msiBody = []byte("MSI VKO-Agent 0.2.0")

// hashOf is the sha256 of data in lower-case hex, as the server sends it.
func hashOf(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

// testLogger writes the log of the agent into the test output.
func testLogger(t *testing.T) *slog.Logger {
	t.Helper()
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}

// TestVerifyMatches: the hash of the downloaded file is the hash of the
// release - the file stays and is installed.
func TestVerifyMatches(t *testing.T) {
	path := filepath.Join(t.TempDir(), "0.2.0.msi")
	if err := os.WriteFile(path, msiBody, 0o644); err != nil {
		t.Fatalf("подготовка файла: %v", err)
	}

	if err := Verify(path, hashOf(msiBody)); err != nil {
		t.Fatalf("Verify совпавшего файла = %v, want nil", err)
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("файл после успешной проверки: %v, want на месте", err)
	}
	// The server declares the hash in lower case; an upper-case one is the
	// same hash and must not be refused.
	if err := Verify(path, strings.ToUpper(hashOf(msiBody))); err != nil {
		t.Fatalf("Verify с хэшем в верхнем регистре = %v, want nil", err)
	}
}

// TestVerifyMismatchDeletesFile: a file whose hash is not the one of the
// release is refused and deleted - nothing is installed from it
// (ТЗ п. 20, plan.md §4.6).
func TestVerifyMismatchDeletesFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "0.2.0.msi")
	if err := os.WriteFile(path, []byte("подменённый файл"), 0o644); err != nil {
		t.Fatalf("подготовка файла: %v", err)
	}

	want := hashOf(msiBody)
	err := Verify(path, want)
	if !errors.Is(err, ErrHashMismatch) {
		t.Fatalf("Verify подменённого файла = %v, want ErrHashMismatch", err)
	}
	if !strings.Contains(err.Error(), want) || !strings.Contains(err.Error(), hashOf([]byte("подменённый файл"))) {
		t.Fatalf("ошибка %q не называет оба хэша", err)
	}
	if _, err := os.Stat(path); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("файл после несовпадения: %v, want удалён", err)
	}
}

func TestVerifyMissingFile(t *testing.T) {
	err := Verify(filepath.Join(t.TempDir(), "нет.msi"), hashOf(msiBody))
	if !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("Verify отсутствующего файла = %v, want os.ErrNotExist", err)
	}
}

func TestNewer(t *testing.T) {
	cases := []struct {
		current, latest string
		want            bool
	}{
		{"0.1.0", "0.2.0", true},
		{"0.2.0", "0.2.1", true},
		{"0.9.0", "1.0.0", true},
		{"1.2.3", "1.10.0", true},
		{"0.2", "0.2.1", true},
		{"0.2.0", "v0.3.0", true},
		{"0.2.0", "0.2.0", false},
		{"0.3.0", "0.2.0", false},
		{"1.0.0", "0.9.9", false},
		// A local build is never updated over: it would lose the code it was
		// built from (T-50).
		{DevVersion, "0.2.0", false},
		{"0.2.0", DevVersion, false},
		{"0.2.0", "", false},
		{"", "0.2.0", false},
		{"0.2.0", "0.2.0-rc1", false},
		{"0.2.0", "0.2.0.1", false},
	}
	for _, c := range cases {
		if got := Newer(c.current, c.latest); got != c.want {
			t.Errorf("Newer(%q, %q) = %v, want %v", c.current, c.latest, got, c.want)
		}
	}
}

// TestDecide is the rule of the rollback: what the version that started after
// msiexec does with the record left by the previous one (T-50).
func TestDecide(t *testing.T) {
	started := time.Date(2026, 9, 17, 9, 0, 0, 0, almaty)
	pending := Pending{
		FromVersion: "0.1.0",
		ToVersion:   "0.2.0",
		MSIPath:     `C:\ProgramData\VKO Monitor\updates\0.2.0.msi`,
		PreviousMSI: `C:\ProgramData\VKO Monitor\updates\0.1.0.msi`,
		StartedAt:   started,
	}
	noPrevious := pending
	noPrevious.PreviousMSI = ""

	cases := []struct {
		name          string
		p             Pending
		current       string
		lastHeartbeat time.Time
		now           time.Time
		want          Decision
	}{
		{
			name:    "новая версия ещё не отчиталась, срок не вышел",
			p:       pending,
			current: "0.2.0",
			now:     started.Add(5 * time.Minute),
			want:    Wait,
		},
		{
			name:          "heartbeat новой версии дошёл",
			p:             pending,
			current:       "0.2.0",
			lastHeartbeat: started.Add(2 * time.Minute),
			now:           started.Add(3 * time.Minute),
			want:          Confirmed,
		},
		{
			name:          "heartbeat прежней версии до обновления не считается",
			p:             pending,
			current:       "0.2.0",
			lastHeartbeat: started.Add(-time.Minute),
			now:           started.Add(5 * time.Minute),
			want:          Wait,
		},
		{
			name:    "срок вышел, новая версия молчит — откат",
			p:       pending,
			current: "0.2.0",
			now:     started.Add(confirmDeadline + time.Minute),
			want:    Rollback,
		},
		{
			name:    "срок вышел, работает прежняя версия — установка не прошла",
			p:       pending,
			current: "0.1.0",
			now:     started.Add(confirmDeadline + time.Minute),
			want:    GiveUp,
		},
		{
			name:    "срок вышел, но прежнего установщика нет — откатывать нечем",
			p:       noPrevious,
			current: "0.2.0",
			now:     started.Add(confirmDeadline + time.Minute),
			want:    GiveUp,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := Decide(c.p, c.current, c.lastHeartbeat, c.now); got != c.want {
				t.Fatalf("Decide = %s, want %s", got, c.want)
			}
		})
	}
}

// TestStateRoundTrip: the record survives the update itself - the version that
// starts after msiexec reads exactly what the previous one wrote.
func TestStateRoundTrip(t *testing.T) {
	dir := t.TempDir()
	if _, err := ReadState(dir); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("ReadState без файла = %v, want os.ErrNotExist", err)
	}

	want := State{
		InstalledMSI: filepath.Join(dir, "updates", "0.1.0.msi"),
		Pending: &Pending{
			FromVersion: "0.1.0",
			ToVersion:   "0.2.0",
			MSIPath:     filepath.Join(dir, "updates", "0.2.0.msi"),
			PreviousMSI: filepath.Join(dir, "updates", "0.1.0.msi"),
			StartedAt:   time.Date(2026, 9, 17, 9, 0, 0, 0, almaty),
		},
		Failed: []string{"0.1.9"},
	}
	if err := WriteState(dir, want); err != nil {
		t.Fatalf("WriteState: %v", err)
	}
	got, err := ReadState(dir)
	if err != nil {
		t.Fatalf("ReadState: %v", err)
	}
	if got.InstalledMSI != want.InstalledMSI || got.Pending == nil {
		t.Fatalf("ReadState = %+v, want %+v", got, want)
	}
	if got.Pending.FromVersion != want.Pending.FromVersion || got.Pending.ToVersion != want.Pending.ToVersion ||
		got.Pending.MSIPath != want.Pending.MSIPath || got.Pending.PreviousMSI != want.Pending.PreviousMSI {
		t.Fatalf("запись = %+v, want %+v", got.Pending, want.Pending)
	}
	// The record goes through JSON: the moment survives, the name of the zone
	// does not (ADR-014), so the times are compared and not the structs.
	if !got.Pending.StartedAt.Equal(want.Pending.StartedAt) {
		t.Fatalf("started_at = %s, want %s", got.Pending.StartedAt, want.Pending.StartedAt)
	}
	if !got.failed("0.1.9") || got.failed("0.2.0") {
		t.Fatalf("failed = %v, want только 0.1.9", got.Failed)
	}
	// markFailed does not repeat a version already written off.
	got = got.markFailed("0.1.9").markFailed("0.2.0")
	if len(got.Failed) != 2 {
		t.Fatalf("failed после markFailed = %v, want две версии", got.Failed)
	}
}

func TestResolveURL(t *testing.T) {
	const server = "https://monitor.example.kz"
	cases := []struct {
		raw      string
		want     string
		wantOurs bool
		wantErr  bool
	}{
		{raw: "/api/agent/releases/0.2.0/VKO-Agent.msi",
			want: "https://monitor.example.kz/api/agent/releases/0.2.0/VKO-Agent.msi", wantOurs: true},
		{raw: "https://monitor.example.kz/files/VKO-Agent.msi",
			want: "https://monitor.example.kz/files/VKO-Agent.msi", wantOurs: true},
		// A mirror is another host: the device token must not go there (ADR-005).
		{raw: "https://mirror.example.kz/VKO-Agent.msi",
			want: "https://mirror.example.kz/VKO-Agent.msi", wantOurs: false},
		{raw: "ftp://monitor.example.kz/VKO-Agent.msi", wantErr: true},
	}
	for _, c := range cases {
		got, ours, err := resolveURL(server, c.raw)
		if c.wantErr {
			if err == nil {
				t.Errorf("resolveURL(%q) = %q, want ошибку", c.raw, got)
			}
			continue
		}
		if err != nil || got != c.want || ours != c.wantOurs {
			t.Errorf("resolveURL(%q) = %q, свой %v, %v; want %q, свой %v",
				c.raw, got, ours, err, c.want, c.wantOurs)
		}
	}
}

// releaseServer answers GET /api/agent/releases/latest with rel and serves
// body at the download address.
func releaseServer(t *testing.T, rel *api.Release, body []byte) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/agent/releases/latest":
			w.Header().Set("Content-Type", "application/json")
			if err := json.NewEncoder(w).Encode(rel); err != nil {
				t.Errorf("ответ о релизе: %v", err)
			}
		case "/files/VKO-Agent.msi":
			if auth := r.Header.Get("Authorization"); auth != "Device tok" {
				t.Errorf("скачивание без токена устройства: Authorization = %q", auth)
			}
			_, _ = w.Write(body)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
}

// TestCheckInstallsNewerVersion: the version the server expects is downloaded,
// its hash checked and the updater started; the record left behind names what
// has to confirm itself and what a rollback returns to (T-50).
func TestCheckInstallsNewerVersion(t *testing.T) {
	rel := api.Release{
		Version:     "0.2.0",
		Channel:     "pilot",
		DownloadURL: "/files/VKO-Agent.msi",
		SHA256:      hashOf(msiBody),
		ReleasedAt:  time.Date(2026, 9, 17, 9, 0, 0, 0, almaty),
	}
	srv := releaseServer(t, &rel, msiBody)
	defer srv.Close()

	dir := t.TempDir()
	started := time.Date(2026, 9, 17, 10, 0, 0, 0, almaty)
	o, run := testOptions(t, dir, srv.URL, "0.1.0", func() string { return "0.2.0" }, started)
	st := State{InstalledMSI: filepath.Join(dir, "updates", "0.1.0.msi")}

	wait, done, err := o.check(context.Background(), st)
	if err != nil || !done {
		t.Fatalf("check = ожидание %s, запущено %v, %v; want запущенный установщик", wait, done, err)
	}

	msi := filepath.Join(UpdatesDir(dir), "0.2.0.msi")
	if run.calls != 1 || run.msi != msi || run.version != "0.2.0" || run.remove != "" {
		t.Fatalf("установщик запущен как %+v, want установка %s без удаления прежней", run, msi)
	}
	if data, err := os.ReadFile(msi); err != nil || string(data) != string(msiBody) {
		t.Fatalf("скачанный файл %s = %q, %v; want содержимое релиза", msi, data, err)
	}
	if _, err := os.Stat(msi + ".part"); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf(".part после скачивания: %v, want переименован", err)
	}
	got, err := ReadState(dir)
	if err != nil {
		t.Fatalf("ReadState: %v", err)
	}
	if got.Pending == nil {
		t.Fatalf("состояние = %+v, want запись о начатом обновлении", got)
	}
	if got.Pending.FromVersion != "0.1.0" || got.Pending.ToVersion != "0.2.0" ||
		got.Pending.MSIPath != msi || got.Pending.PreviousMSI != st.InstalledMSI ||
		!got.Pending.StartedAt.Equal(started) {
		t.Fatalf("запись = %+v, want обновление 0.1.0 → 0.2.0 с прежним установщиком", got.Pending)
	}
}

// TestCheckRefusesHashMismatch: the file the server sent is not the file its
// sha256 describes - nothing is installed, the file is gone and the version is
// not tried again (ТЗ п. 20).
func TestCheckRefusesHashMismatch(t *testing.T) {
	rel := api.Release{
		Version:     "0.2.0",
		Channel:     "pilot",
		DownloadURL: "/files/VKO-Agent.msi",
		// The hash of another file: this is a substituted or a broken release.
		SHA256:     hashOf([]byte("другой файл")),
		ReleasedAt: time.Date(2026, 9, 17, 9, 0, 0, 0, almaty),
	}
	srv := releaseServer(t, &rel, msiBody)
	defer srv.Close()

	dir := t.TempDir()
	o, run := testOptions(t, dir, srv.URL, "0.1.0", func() string { return "0.2.0" },
		time.Date(2026, 9, 17, 10, 0, 0, 0, almaty))

	_, done, err := o.check(context.Background(), State{})
	if err != nil || done {
		t.Fatalf("check с неверным хэшем = запущено %v, %v; want отказ без установки", done, err)
	}
	if run.calls != 0 {
		t.Fatalf("установщик запущен %d раз, want ни разу: хэш не совпал", run.calls)
	}
	if _, err := os.Stat(filepath.Join(UpdatesDir(dir), "0.2.0.msi")); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("файл после несовпадения хэша: %v, want удалён", err)
	}
	st, err := ReadState(dir)
	if err != nil {
		t.Fatalf("ReadState: %v", err)
	}
	if st.Pending != nil || !st.failed("0.2.0") {
		t.Fatalf("состояние = %+v, want без начатого обновления и с отметкой о неудачной версии", st)
	}

	// The refused version is not downloaded again while the server keeps
	// offering it.
	if _, done, err := o.check(context.Background(), st); err != nil || done {
		t.Fatalf("повторный check = запущено %v, %v; want пропуск", done, err)
	}
}

// TestCheckSkipsSameVersion: the server expects the version that is already
// running - the release is not even asked for.
func TestCheckSkipsSameVersion(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Errorf("лишний запрос %s %s", r.Method, r.URL.Path)
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	dir := t.TempDir()
	o, _ := testOptions(t, dir, srv.URL, "0.2.0", func() string { return "0.2.0" }, time.Now())
	if _, done, err := o.check(context.Background(), State{}); err != nil || done {
		t.Fatalf("check той же версии = запущено %v, %v; want ничего", done, err)
	}
}

// TestCheckNoReleaseOnChannel: the configuration names a version the channel
// does not have yet - it is a warning, not a failure with a backoff.
func TestCheckNoReleaseOnChannel(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/problem+json")
		w.WriteHeader(http.StatusNotFound)
		_, _ = w.Write([]byte(`{"type": "not_found", "title": "Релиз не найден", "status": 404}`))
	}))
	defer srv.Close()

	dir := t.TempDir()
	o, _ := testOptions(t, dir, srv.URL, "0.1.0", func() string { return "0.2.0" }, time.Now())
	wait, done, err := o.check(context.Background(), State{})
	if err != nil || done || wait != checkInterval {
		t.Fatalf("check без релиза = ожидание %s, запущено %v, %v; want обычная пауза без ошибки",
			wait, done, err)
	}
}

// TestResolveConfirms: the new version runs and the server accepted its
// heartbeat - the record is cleared, the file it was installed from becomes
// the one a next rollback returns to, and the previous one is deleted.
func TestResolveConfirms(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(UpdatesDir(dir), 0o755); err != nil {
		t.Fatalf("папка обновлений: %v", err)
	}
	previous := filepath.Join(UpdatesDir(dir), "0.1.0.msi")
	current := filepath.Join(UpdatesDir(dir), "0.2.0.msi")
	for _, path := range []string{previous, current} {
		if err := os.WriteFile(path, msiBody, 0o644); err != nil {
			t.Fatalf("подготовка файла: %v", err)
		}
	}

	started := time.Date(2026, 9, 17, 10, 0, 0, 0, almaty)
	o, run := testOptions(t, dir, "https://monitor.example.kz", "0.2.0", nil, started.Add(3*time.Minute))
	o.LastHeartbeat = func() time.Time { return started.Add(2 * time.Minute) }
	st := State{Pending: &Pending{
		FromVersion: "0.1.0",
		ToVersion:   "0.2.0",
		MSIPath:     current,
		PreviousMSI: previous,
		StartedAt:   started,
	}}

	if _, done, err := o.resolve(st); err != nil || done {
		t.Fatalf("resolve = запущено %v, %v; want подтверждение без установщика", done, err)
	}
	got, err := ReadState(dir)
	if err != nil {
		t.Fatalf("ReadState: %v", err)
	}
	if got.Pending != nil || got.InstalledMSI != current {
		t.Fatalf("состояние = %+v, want без записи и с установщиком текущей версии", got)
	}
	if run.calls != 0 {
		t.Fatalf("установщик запущен %d раз, want ни разу: обновление подтверждено", run.calls)
	}
	if _, err := os.Stat(previous); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("установщик прежней версии: %v, want удалён после подтверждения", err)
	}
}

// TestResolveGivesUpWithoutPreviousMSI: the first self-update has no file of
// the version it replaced, so there is nothing to roll back to - the record is
// cleared and the version is written off (docs/known-limitations.md).
func TestResolveGivesUpWithoutPreviousMSI(t *testing.T) {
	dir := t.TempDir()
	started := time.Date(2026, 9, 17, 10, 0, 0, 0, almaty)
	o, run := testOptions(t, dir, "https://monitor.example.kz", "0.2.0", nil,
		started.Add(confirmDeadline+time.Minute))
	st := State{Pending: &Pending{
		FromVersion: "0.1.0",
		ToVersion:   "0.2.0",
		MSIPath:     filepath.Join(UpdatesDir(dir), "0.2.0.msi"),
		StartedAt:   started,
	}}

	if _, done, err := o.resolve(st); err != nil || done {
		t.Fatalf("resolve = запущено %v, %v; want отказ без установщика", done, err)
	}
	got, err := ReadState(dir)
	if err != nil {
		t.Fatalf("ReadState: %v", err)
	}
	if got.Pending != nil || !got.failed("0.2.0") {
		t.Fatalf("состояние = %+v, want без записи и с отметкой о неудачной версии", got)
	}
	if run.calls != 0 {
		t.Fatalf("установщик запущен %d раз, want ни разу: откатывать нечем", run.calls)
	}
}

// TestResolveRollsBack: the deadline passed and the server never heard the new
// version - the previous installer is put back, and the new installation is
// removed first, because the package refuses a downgrade (T-50).
func TestResolveRollsBack(t *testing.T) {
	dir := t.TempDir()
	previous := filepath.Join(UpdatesDir(dir), "0.1.0.msi")
	current := filepath.Join(UpdatesDir(dir), "0.2.0.msi")
	started := time.Date(2026, 9, 17, 10, 0, 0, 0, almaty)
	o, run := testOptions(t, dir, "https://monitor.example.kz", "0.2.0", nil,
		started.Add(confirmDeadline+time.Minute))
	st := State{InstalledMSI: current, Pending: &Pending{
		FromVersion: "0.1.0",
		ToVersion:   "0.2.0",
		MSIPath:     current,
		PreviousMSI: previous,
		StartedAt:   started,
	}}

	_, done, err := o.resolve(st)
	if err != nil || !done {
		t.Fatalf("resolve = запущено %v, %v; want запущенный откат", done, err)
	}
	if run.calls != 1 || run.msi != previous || run.version != "0.1.0" || run.remove != current {
		t.Fatalf("откат запущен как %+v, want установку %s со снятием %s", run, previous, current)
	}
	got, err := ReadState(dir)
	if err != nil {
		t.Fatalf("ReadState: %v", err)
	}
	if got.Pending != nil || got.InstalledMSI != previous || !got.failed("0.2.0") {
		t.Fatalf("состояние = %+v, want возврат к прежнему установщику и отметку о неудачной версии", got)
	}
}

// TestUpdaterCopy: the updater runs from a copy beside the releases, not from
// the installed binary - msiexec cannot replace the image of a running
// process (plan.md §4.6).
func TestUpdaterCopy(t *testing.T) {
	dir := t.TempDir()
	exe := filepath.Join(dir, "vko-agent.exe")
	if err := os.WriteFile(exe, []byte("агент 0.1.0"), 0o755); err != nil {
		t.Fatalf("подготовка файла: %v", err)
	}
	o, _ := testOptions(t, dir, "https://monitor.example.kz", "0.1.0", nil, time.Now())
	o.ExePath = exe

	path, err := o.updaterCopy("0.2.0")
	if err != nil {
		t.Fatalf("updaterCopy: %v", err)
	}
	if path == exe || filepath.Dir(path) != UpdatesDir(dir) || filepath.Ext(path) != ".exe" {
		t.Fatalf("копия = %s, want файл .exe в %s", path, UpdatesDir(dir))
	}
	data, err := os.ReadFile(path)
	if err != nil || string(data) != "агент 0.1.0" {
		t.Fatalf("копия = %q, %v; want содержимое агента", data, err)
	}
	info, err := os.Stat(path)
	if err != nil || info.Mode().Perm()&0o100 == 0 {
		t.Fatalf("права копии = %v, %v; want исполняемый файл", info.Mode(), err)
	}
}

// launched is the updater process the options of a test would have started.
type launched struct {
	msi, version, remove string
	calls                int
}

// testOptions builds the options of a running agent for the tests. The start
// of the updater is recorded instead of done: no msiexec runs in `make check`.
func testOptions(t *testing.T, dir, serverURL, version string, latest func() string, now time.Time) (Options, *launched) {
	t.Helper()
	if latest == nil {
		latest = func() string { return "" }
	}
	var last launched
	o, err := Options{
		DataDir:       dir,
		ConfigPath:    filepath.Join(dir, "agent.yaml"),
		ServerURL:     serverURL,
		Client:        api.New(serverURL, "tok"),
		Version:       version,
		LatestVersion: latest,
		ExePath:       filepath.Join(dir, "vko-agent"),
		Logger:        testLogger(t),
		Now:           func() time.Time { return now },
		launcher: func(msi, version, remove string) error {
			last = launched{msi: msi, version: version, remove: remove, calls: last.calls + 1}
			return nil
		},
	}.withDefaults()
	if err != nil {
		t.Fatalf("Options: %v", err)
	}
	return o, &last
}
