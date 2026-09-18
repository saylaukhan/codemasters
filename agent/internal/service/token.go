package service

import (
	"context"
	"log/slog"
	"path/filepath"

	"github.com/saylaukhan/codemasters/agent/internal/api"
	"github.com/saylaukhan/codemasters/agent/internal/secure"
)

// rotateToken exchanges the device token when the configuration asks for it
// (token_rotation_required, T-36, ADR-005). The old token stops working as
// soon as the server answers, so the new one is saved first and then given to
// the client every goroutine shares. It reports whether the token changed.
//
// A lost answer cannot be asked for again: the agent is left without a valid
// token and is registered again with a new installation code of its school.
func rotateToken(ctx context.Context, client *api.Client, dataDir string, logger *slog.Logger) bool {
	resp, err := client.RotateToken(ctx)
	if err != nil {
		logger.Warn("токен устройства не заменён, повтор при следующем обновлении конфигурации", "err", err)
		return false
	}
	if err := secure.WriteSecret(filepath.Join(dataDir, tokenFileName), []byte(resp.DeviceToken)); err != nil {
		// The new token still works until a restart; after it a new code is needed.
		logger.Error("новый токен устройства не сохранён: после перезапуска нужна регистрация по новому коду",
			"device_id", resp.DeviceID, "err", err)
	}
	client.SetToken(resp.DeviceToken)
	logger.Info("токен устройства заменён по запросу администратора", "device_id", resp.DeviceID)
	return true
}
