use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub redis_url: String,
    pub supabase_url: String,
    pub supabase_key: String,
    #[serde(default = "default_supabase_bucket")]
    pub supabase_providers_bucket: String,
    pub ai_proveedores_internal_token: String,
    pub rust_onboarding_test_numbers: String,
    pub openai_api_key: String,
    #[serde(default = "default_openai_base_url")]
    pub openai_base_url: String,
    #[serde(default = "default_openai_embedding_model")]
    pub openai_embedding_model: String,
    #[serde(default = "default_stream_key")]
    pub provider_onboarding_stream_key: String,
    #[serde(default = "default_stream_maxlen")]
    pub provider_onboarding_stream_maxlen: u64,
    #[serde(default = "default_async_persistence")]
    pub provider_onboarding_async_persistence_enabled: bool,
    #[serde(default = "default_rust_log")]
    pub rust_log: String,
    #[serde(default = "default_port")]
    pub port: u16,
    #[serde(default = "default_bind_addr")]
    pub bind_addr: String,
}

impl Config {
    pub fn from_env() -> Result<Self, envy::Error> {
        envy::from_env()
    }

    pub fn test_numbers(&self) -> Vec<String> {
        self.rust_onboarding_test_numbers
            .split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(ToOwned::to_owned)
            .collect()
    }
}

fn default_stream_key() -> String { "provider_onboarding_events".to_string() }
fn default_stream_maxlen() -> u64 { 10_000 }
fn default_async_persistence() -> bool { true }
fn default_rust_log() -> String { "info".to_string() }
fn default_port() -> u16 { 8003 }
fn default_bind_addr() -> String { "0.0.0.0".to_string() }
fn default_supabase_bucket() -> String { "tinkubot-providers".to_string() }
fn default_openai_base_url() -> String { "https://api.openai.com/v1".to_string() }
fn default_openai_embedding_model() -> String { "text-embedding-3-small".to_string() }
