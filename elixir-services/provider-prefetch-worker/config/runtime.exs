import Config

config :provider_prefetch_worker,
  redis_url: System.get_env("REDIS_URL", "redis://redis:6379"),
  stream_key:
    System.get_env("PROVIDER_PREFETCH_STREAM_KEY", "client_search_prefetch_events"),
  stream_group:
    System.get_env("PROVIDER_PREFETCH_STREAM_GROUP", "provider-prefetch-workers"),
  consumer_name:
    System.get_env("PROVIDER_PREFETCH_CONSUMER_NAME", "provider-prefetch-worker-1"),
  block_ms:
    String.to_integer(System.get_env("PROVIDER_PREFETCH_STREAM_BLOCK_MS", "5000")),
  batch_size:
    String.to_integer(System.get_env("PROVIDER_PREFETCH_STREAM_BATCH_SIZE", "10")),
  claim_idle_ms:
    String.to_integer(System.get_env("PROVIDER_PREFETCH_STREAM_CLAIM_IDLE_MS", "15000")),
  max_attempts:
    String.to_integer(System.get_env("PROVIDER_PREFETCH_MAX_ATTEMPTS", "2")),
  status_ttl_seconds:
    String.to_integer(System.get_env("PROVIDER_PREFETCH_STATUS_TTL_SECONDS", "300")),
  result_ttl_seconds:
    String.to_integer(System.get_env("PROVIDER_PREFETCH_RESULT_TTL_SECONDS", "120")),
  ai_search_url: System.get_env("AI_SEARCH_URL", "http://ai-search:8000"),
  ai_search_internal_token: System.get_env("AI_SEARCH_INTERNAL_TOKEN", ""),
  ai_search_timeout_ms:
    String.to_integer(System.get_env("PROVIDER_PREFETCH_SEARCH_TIMEOUT_MS", "8000"))
