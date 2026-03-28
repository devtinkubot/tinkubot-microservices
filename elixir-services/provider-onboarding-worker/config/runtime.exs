import Config

config :provider_onboarding_worker,
  redis_url: System.get_env("REDIS_URL", "redis://redis:6379"),
  stream_key: System.get_env("PROVIDER_ONBOARDING_STREAM_KEY", "provider_onboarding_events"),
  stream_group: System.get_env("PROVIDER_ONBOARDING_STREAM_GROUP", "provider-onboarding-workers"),
  dlq_stream_key:
    System.get_env(
      "PROVIDER_ONBOARDING_DLQ_STREAM_KEY",
      "provider_onboarding_events_dlq"
    ),
  consumer_name:
    System.get_env(
      "PROVIDER_ONBOARDING_CONSUMER_NAME",
      "provider-onboarding-worker-1"
    ),
  block_ms: String.to_integer(System.get_env("PROVIDER_ONBOARDING_STREAM_BLOCK_MS", "5000")),
  batch_size: String.to_integer(System.get_env("PROVIDER_ONBOARDING_STREAM_BATCH_SIZE", "10")),
  claim_idle_ms:
    String.to_integer(System.get_env("PROVIDER_ONBOARDING_STREAM_CLAIM_IDLE_MS", "30000")),
  max_attempts: String.to_integer(System.get_env("PROVIDER_ONBOARDING_STREAM_MAX_ATTEMPTS", "5")),
  status_ttl_seconds:
    String.to_integer(System.get_env("PROVIDER_ONBOARDING_STATUS_TTL_SECONDS", "172800")),
  supabase_url: System.get_env("SUPABASE_URL", ""),
  supabase_service_key: System.get_env("SUPABASE_SERVICE_KEY", ""),
  ai_proveedores_url: System.get_env("AI_PROVEEDORES_URL", "http://ai-proveedores:8002"),
  ai_proveedores_internal_token: System.get_env("AI_PROVEEDORES_INTERNAL_TOKEN", ""),
  providers_bucket: System.get_env("SUPABASE_PROVIDERS_BUCKET", "tinkubot-providers"),
  openai_api_key: System.get_env("OPENAI_API_KEY", ""),
  openai_embedding_model:
    System.get_env("PROVIDER_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
