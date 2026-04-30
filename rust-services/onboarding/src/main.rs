use std::time::Duration;

use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde_json::json;
use validator::Validate;
use tower_http::{
    limit::RequestBodyLimitLayer,
    timeout::TimeoutLayer,
    trace::TraceLayer,
};

mod config;
mod errors;
mod events;
mod flow;
mod handlers;
mod middleware;
mod openai;
mod logic;
mod normalize;
mod models;
mod router;
mod store;
mod supabase;
mod templates;

use config::Config;
use errors::AppError;
use models::{OnboardingResponse, WebhookPayload};
use openai::OpenAIClient;
use store::RedisStore;
use supabase::SupabaseClient;

#[derive(Clone)]
pub struct AppState {
    pub config: Config,
    pub store: RedisStore,
    pub supabase: SupabaseClient,
    pub openai: OpenAIClient,
}

#[tokio::main]
async fn main() -> Result<(), AppError> {
    let config = Config::from_env()?;
    let _ = tracing_subscriber::fmt()
        .json()
        .with_current_span(true)
        .with_span_list(true)
        .with_target(false)
        .with_max_level(parse_level(&config.rust_log))
        .try_init();

    let redis_cfg = deadpool_redis::Config::from_url(config.redis_url.clone());
    let pool = redis_cfg
        .create_pool(Some(deadpool_redis::Runtime::Tokio1))
        .map_err(|err| AppError::PoolCreate(err.to_string()))?;

    let state = AppState {
        config: config.clone(),
        store: RedisStore::new(pool),
        supabase: SupabaseClient::new(
            config.supabase_url.clone(),
            config.supabase_key.clone(),
            config.supabase_providers_bucket.clone(),
        ),
        openai: OpenAIClient::new(
            config.openai_base_url.clone(),
            config.openai_api_key.clone(),
            config.openai_embedding_model.clone(),
        ),
    };

    let app = build_app(state);
    let bind_addr = format!("{}:{}", config.bind_addr, config.port);
    let listener = tokio::net::TcpListener::bind(&bind_addr).await?;
    axum::serve(listener, app).await?;
    Ok(())
}

fn build_app(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/handle-whatsapp-message", post(handle_whatsapp_message))
        .layer(RequestBodyLimitLayer::new(10 * 1024 * 1024))
        .layer(TimeoutLayer::with_status_code(
            StatusCode::REQUEST_TIMEOUT,
            Duration::from_secs(10),
        ))
        .layer(TraceLayer::new_for_http())
        .with_state(state)
}

async fn health() -> Json<serde_json::Value> {
    Json(json!({ "status": "ok" }))
}

async fn handle_whatsapp_message(
    State(state): State<AppState>,
    _internal: middleware::InternalOnly,
    Json(payload): Json<WebhookPayload>,
) -> Result<Json<OnboardingResponse>, AppError> {
    payload.validate()?;
    let response = router::dispatch(state, payload).await?;
    Ok(Json(response))
}

fn parse_level(value: &str) -> tracing::Level {
    match value.to_ascii_lowercase().as_str() {
        "trace" => tracing::Level::TRACE,
        "debug" => tracing::Level::DEBUG,
        "warn" => tracing::Level::WARN,
        "error" => tracing::Level::ERROR,
        _ => tracing::Level::INFO,
    }
}
