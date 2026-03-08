package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/tinkubot/wa-gateway/internal/api"
	"github.com/tinkubot/wa-gateway/internal/metaoutbound"
	"github.com/tinkubot/wa-gateway/internal/metawebhook"
	"github.com/tinkubot/wa-gateway/internal/outbound"
	"github.com/tinkubot/wa-gateway/internal/ratelimit"
	"github.com/tinkubot/wa-gateway/internal/webhook"
	"github.com/tinkubot/wa-gateway/internal/whatsmeow"
)

func main() {
	// Parse command-line flags
	healthcheck := flag.Bool("healthcheck", false, "Run health check and exit")
	flag.Parse()

	log.Println("🚀 Starting wa-gateway...")

	port := os.Getenv("GATEWAY_PORT")
	if port == "" {
		port = "7000"
	}

	// SQLite database path (can be overridden via env var)
	databasePath := os.Getenv("DATABASE_PATH")
	if databasePath == "" {
		databasePath = "file:./data/wa-gateway.db?_foreign_keys=on"
	}

	// If healthcheck flag is set, run healthcheck and exit
	if *healthcheck {
		runHealthcheck(databasePath)
		return
	}

	// Create rate limiter (in-memory)
	rateLimitConfig := ratelimit.Config{
		MaxPerHour: parseIntEnv("RATE_LIMIT_MAX_PER_HOUR", 20),
		MaxPer24h:  parseIntEnv("RATE_LIMIT_MAX_PER_24H", 100),
	}
	rl := ratelimit.NewLimiter(rateLimitConfig)
	log.Println("✅ Rate limiter initialized (in-memory)")

	// Create webhook client with dynamic routing
	aiClientesURL := os.Getenv("AI_CLIENTES_URL")
	if aiClientesURL == "" {
		aiClientesURL = "http://ai-clientes:8001"
	}
	aiProveedoresURL := os.Getenv("AI_PROVEEDORES_URL")
	if aiProveedoresURL == "" {
		aiProveedoresURL = "http://ai-proveedores:8002"
	}
	webhookEndpoint := os.Getenv("WEBHOOK_ENDPOINT")
	if webhookEndpoint == "" {
		webhookEndpoint = "/handle-whatsapp-message"
	}
	webhookTimeout := parseIntEnv("WEBHOOK_TIMEOUT_MS", 10000)
	webhookRetryAttempts := parseIntEnv("WEBHOOK_RETRY_ATTEMPTS", 3)

	webhookClient := webhook.NewWebhookClient(
		aiClientesURL,
		aiProveedoresURL,
		webhookEndpoint,
		webhookTimeout,
		webhookRetryAttempts,
	)
	log.Printf("✅ Webhook client created - clientes: %s%s, proveedores: %s%s",
		aiClientesURL, webhookEndpoint, aiProveedoresURL, webhookEndpoint)

	// Create client manager with SQLite and webhook client
	cm, err := whatsmeow.NewClientManager(databasePath, webhookClient)
	if err != nil {
		log.Fatalf("❌ Failed to create client manager: %v", err)
	}
	log.Println("✅ Client manager created (SQLite)")

	// Create SSE hub
	sseHub := api.NewSSEHub()
	log.Println("✅ SSE hub created")

	// Add SSE broadcaster to client manager
	cm.AddEventHandler(func(event whatsmeow.Event) {
		sseHub.Broadcast(event)
	})

	// Create API handlers
	metaEnabled := parseBoolEnv("WA_META_WEBHOOK_ENABLED", false)
	metaVerifyToken := strings.TrimSpace(os.Getenv("META_WEBHOOK_VERIFY_TOKEN"))
	metaAppSecret := strings.TrimSpace(os.Getenv("META_APP_SECRET"))
	metaClientesPhoneNumberID := strings.TrimSpace(os.Getenv("META_PHONE_NUMBER_ID_CLIENTES"))
	metaProveedoresPhoneNumberID := strings.TrimSpace(os.Getenv("META_PHONE_NUMBER_ID_PROVEEDORES"))
	metaOutboundEnabled := parseBoolEnv("WA_META_OUTBOUND_ENABLED", false)
	metaEnabledAccounts := parseEnabledAccounts(os.Getenv("WA_META_ENABLED_ACCOUNTS"))
	metaGraphBaseURL := strings.TrimSpace(os.Getenv("META_GRAPH_BASE_URL"))
	metaGraphAPIVersion := strings.TrimSpace(os.Getenv("META_GRAPH_API_VERSION"))
	metaClientesAccessToken := strings.TrimSpace(os.Getenv("META_CLIENTES_ACCESS_TOKEN"))
	metaProveedoresAccessToken := strings.TrimSpace(os.Getenv("META_PROVEEDORES_ACCESS_TOKEN"))

	if metaEnabled {
		if metaVerifyToken == "" {
			log.Fatal("❌ WA_META_WEBHOOK_ENABLED=true but META_WEBHOOK_VERIFY_TOKEN is empty")
		}
		if metaAppSecret == "" {
			log.Fatal("❌ WA_META_WEBHOOK_ENABLED=true but META_APP_SECRET is empty")
		}
		if metaClientesPhoneNumberID == "" && metaProveedoresPhoneNumberID == "" {
			log.Fatal("❌ WA_META_WEBHOOK_ENABLED=true but no META_PHONE_NUMBER_ID_* is configured")
		}
	}
	phoneNumberToAccount := map[string]string{}
	accountToPhoneNumber := map[string]string{}
	if metaClientesPhoneNumberID != "" {
		phoneNumberToAccount[metaClientesPhoneNumberID] = "bot-clientes"
		accountToPhoneNumber["bot-clientes"] = metaClientesPhoneNumberID
	}
	if metaProveedoresPhoneNumberID != "" {
		phoneNumberToAccount[metaProveedoresPhoneNumberID] = "bot-proveedores"
		accountToPhoneNumber["bot-proveedores"] = metaProveedoresPhoneNumberID
	}
	accountAccessTokens := map[string]string{}
	if metaClientesAccessToken != "" {
		accountAccessTokens["bot-clientes"] = metaClientesAccessToken
	}
	if metaProveedoresAccessToken != "" {
		accountAccessTokens["bot-proveedores"] = metaProveedoresAccessToken
	}

	if metaEnabled {
		for accountID, phoneNumberID := range accountToPhoneNumber {
			if !isMetaAccountEnabled(metaEnabled, metaEnabledAccounts, accountToPhoneNumber, accountID) {
				continue
			}
			if strings.TrimSpace(phoneNumberID) == "" {
				log.Fatalf("❌ WA_META_WEBHOOK_ENABLED=true but phone_number_id is empty for account=%s", accountID)
			}
		}
	}
	if metaOutboundEnabled {
		for accountID := range accountToPhoneNumber {
			if !isMetaAccountEnabled(metaOutboundEnabled, metaEnabledAccounts, accountToPhoneNumber, accountID) {
				continue
			}
			if strings.TrimSpace(accountAccessTokens[accountID]) == "" {
				log.Fatalf("❌ WA_META_OUTBOUND_ENABLED=true but access token is empty for account=%s", accountID)
			}
		}
	}

	var metaOutboundClient *metaoutbound.Client
	if metaOutboundEnabled {
		accessTokensByPhoneNumber := map[string]string{}
		for accountID, phoneNumberID := range accountToPhoneNumber {
			token := strings.TrimSpace(accountAccessTokens[accountID])
			if phoneNumberID == "" || token == "" {
				continue
			}
			accessTokensByPhoneNumber[phoneNumberID] = token
		}
		metaOutboundClient = metaoutbound.NewClient(metaoutbound.Config{
			BaseURL:       metaGraphBaseURL,
			APIVersion:    metaGraphAPIVersion,
			AccessToken:   metaClientesAccessToken,
			AccessTokens:  accessTokensByPhoneNumber,
			Timeout:       15 * time.Second,
			RetryAttempts: 2,
		})
		log.Printf("✅ Meta outbound enabled (base_url=%s api_version=%s)", valueOrDefault(metaGraphBaseURL, "https://graph.facebook.com"), valueOrDefault(metaGraphAPIVersion, "v25.0"))
	}

	metaSvc := metawebhook.NewService(
		metawebhook.Config{
			Enabled:              metaEnabled,
			VerifyToken:          metaVerifyToken,
			AppSecret:            metaAppSecret,
			OutboundEnabled:      metaOutboundEnabled,
			EnabledAccounts:      metaEnabledAccounts,
			PhoneNumberToAccount: phoneNumberToAccount,
		},
		webhookClient,
		metaOutboundClient,
		metaOutboundClient,
	)

	outboundRouter := outbound.NewRouter(cm, metaOutboundClient, outbound.RouterConfig{
		MetaOutboundEnabled: metaOutboundEnabled,
		MetaEnabledAccounts: metaEnabledAccounts,
		AccountPhoneNumber:  accountToPhoneNumber,
	})

	metaManagedAccounts := map[string]bool{}
	for accountID := range accountToPhoneNumber {
		if isMetaAccountEnabled(metaEnabled || metaOutboundEnabled, metaEnabledAccounts, accountToPhoneNumber, accountID) {
			metaManagedAccounts[accountID] = true
		}
	}

	handlers := api.NewHandlers(cm, rl, sseHub, metaSvc, outboundRouter, api.HandlerConfig{
		MetaManagedAccounts: metaManagedAccounts,
	})

	// Start WhatsApp clients
	log.Println("📱 Starting WhatsApp clients...")
	accountIDs := []string{"bot-clientes", "bot-proveedores"}
	for _, accountID := range accountIDs {
		if accountID == "bot-proveedores" && metaManagedAccounts[accountID] {
			log.Printf("ℹ️ Skipping whatsmeow startup for %s because Meta is active", accountID)
			continue
		}
		if err := cm.StartClient(accountID); err != nil {
			log.Printf("⚠️  Failed to start client %s: %v", accountID, err)
		}
	}

	// Set up Gin router
	gin.SetMode(gin.ReleaseMode)
	router := gin.Default()

	// Health check (no auth)
	router.GET("/health", handlers.GetHealth)
	router.GET("/meta/webhook", handlers.GetMetaWebhook)
	router.POST("/meta/webhook", handlers.PostMetaWebhook)

	// API routes
	apiGroup := router.Group("/api")
	{
		// Accounts
		apiGroup.GET("/accounts", handlers.GetAccounts)
		apiGroup.GET("/accounts/:accountId", handlers.GetAccount)
		apiGroup.GET("/accounts/:accountId/qr", handlers.GetQR)
		apiGroup.POST("/accounts/:accountId/login", handlers.PostLogin)
		apiGroup.POST("/accounts/:accountId/logout", handlers.PostLogout)

		// Messages
		apiGroup.POST("/send", handlers.PostSend)

		// SSE
		apiGroup.GET("/events/stream", handlers.EventStream)
	}

	// Also expose routes without /api prefix for compatibility
	router.GET("/accounts", handlers.GetAccounts)
	router.GET("/accounts/:accountId", handlers.GetAccount)
	router.GET("/accounts/:accountId/qr", handlers.GetQR)
	router.POST("/accounts/:accountId/login", handlers.PostLogin)
	router.POST("/accounts/:accountId/logout", handlers.PostLogout)
	router.POST("/send", handlers.PostSend)
	router.GET("/events/stream", handlers.EventStream)

	// Start HTTP server
	srv := &http.Server{
		Addr:    ":" + port,
		Handler: router,
	}

	// Graceful shutdown handling
	go func() {
		log.Printf("🌐 HTTP server listening on port %s", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("❌ Failed to start HTTP server: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("🛑 Shutting down server...")

	// Graceful shutdown with 30 second timeout
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Printf("❌ Server forced to shutdown: %v", err)
	}

	log.Println("✅ Server shutdown complete")
}

func valueOrDefault(value, fallback string) string {
	if strings.TrimSpace(value) == "" {
		return fallback
	}
	return value
}

func parseIntEnv(key string, defaultValue int) int {
	val := os.Getenv(key)
	if val == "" {
		return defaultValue
	}
	var result int
	if _, err := fmt.Sscanf(val, "%d", &result); err != nil {
		log.Printf("⚠️  Invalid value for %s: %s, using default: %d", key, val, defaultValue)
		return defaultValue
	}
	return result
}

func parseBoolEnv(key string, defaultValue bool) bool {
	val := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if val == "" {
		return defaultValue
	}
	switch val {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		log.Printf("⚠️ Invalid bool value for %s: %s, using default: %v", key, val, defaultValue)
		return defaultValue
	}
}

func parseEnabledAccounts(raw string) map[string]bool {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return map[string]bool{}
	}

	allowed := make(map[string]bool)
	for _, item := range strings.Split(raw, ",") {
		item = strings.TrimSpace(item)
		if item == "" {
			continue
		}
		allowed[item] = true
	}
	return allowed
}

func isMetaAccountEnabled(enabled bool, allowList map[string]bool, accountToPhoneNumber map[string]string, accountID string) bool {
	if !enabled {
		return false
	}
	if len(allowList) > 0 {
		return allowList[accountID]
	}
	_, exists := accountToPhoneNumber[accountID]
	return exists
}

// runHealthcheck performs a health check and exits with appropriate code
func runHealthcheck(databasePath string) {
	_, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Try to create client manager (will fail if SQLite is broken)
	// Note: webhookClient is nil during healthcheck, which is fine
	_, err := whatsmeow.NewClientManager(databasePath, nil)
	if err != nil {
		log.Printf("❌ Health check failed: cannot initialize SQLite: %v", err)
		os.Exit(1)
	}

	// All checks passed
	log.Println("✅ Health check passed")
	os.Exit(0)
}
