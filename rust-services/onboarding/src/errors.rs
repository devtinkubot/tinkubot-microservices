use axum::{http::StatusCode, response::{IntoResponse, Response}, Json};
use serde::Serialize;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("config error: {0}")]
    Config(#[from] envy::Error),
    #[error("redis pool error: {0}")]
    Pool(#[from] deadpool_redis::PoolError),
    #[error("redis error: {0}")]
    Redis(#[from] deadpool_redis::redis::RedisError),
    #[error("json error: {0}")]
    Json(#[from] serde_json::Error),
    #[error("validation error: {0}")]
    Validation(#[from] validator::ValidationErrors),
    #[error("unauthorized")]
    Unauthorized,
    #[error("unknown state: {0}")]
    UnknownState(String),
    #[error("missing flow for phone: {0}")]
    MissingFlow(String),
    #[error("bad request: {0}")]
    BadRequest(String),
    #[error("http error: {0}")]
    Http(#[from] reqwest::Error),
    #[error("io error: {0}")]
    Io(#[from] std::io::Error),
    #[error("redis pool creation error: {0}")]
    PoolCreate(String),
}

#[derive(Debug, Serialize)]
struct ErrorBody {
    success: bool,
    error: String,
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = match self {
            AppError::Unauthorized => StatusCode::UNAUTHORIZED,
            AppError::Validation(_) | AppError::BadRequest(_) => StatusCode::BAD_REQUEST,
            AppError::UnknownState(_) | AppError::MissingFlow(_) => StatusCode::NOT_FOUND,
            _ => StatusCode::INTERNAL_SERVER_ERROR,
        };
        let body = Json(ErrorBody { success: false, error: self.to_string() });
        (status, body).into_response()
    }
}
