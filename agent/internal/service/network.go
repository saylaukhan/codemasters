package service

import (
	"context"
	"log/slog"
	"time"

	"github.com/saylaukhan/codemasters/agent/internal/netinfo"
	"github.com/saylaukhan/codemasters/agent/internal/probe"
)

// networkSettle is how long the service waits after an adapter change before
// checking the connection: DHCP, Wi-Fi and a VPN need a moment to come up
// (plan.md §4.2). A variable for tests.
var networkSettle = 30 * time.Second

// watchNetwork reacts to a change of the adapters until ctx is done: it waits
// networkSettle, checks the connection to the server and, when the connection
// is up, wakes the queue so that what was measured offline goes at once
// (ТЗ п. 2, ADR-006). Everything it does is in the service log.
func watchNetwork(ctx context.Context, serverURL string, wake chan<- struct{}, logger *slog.Logger) {
	netinfo.Watch(ctx, netinfo.WatchInterval, func(change string) {
		logger.Info("смена сети", "change", change, "check_in", networkSettle)
		select {
		case <-ctx.Done():
			return
		case <-time.After(networkSettle):
		}
		if err := probe.Check(ctx, serverURL); err != nil {
			if ctx.Err() != nil {
				return
			}
			logger.Warn("после смены сети связи с сервером нет", "err", err)
			return
		}
		logger.Info("после смены сети связь есть, досылаем очередь")
		select {
		case wake <- struct{}{}:
		default: // a wake-up is already pending
		}
	})
}
