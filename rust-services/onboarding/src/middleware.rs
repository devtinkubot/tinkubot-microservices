use axum::{
    extract::FromRequestParts,
    http::request::Parts,
};
use subtle::ConstantTimeEq;

use crate::{errors::AppError, AppState};

pub struct InternalOnly;

impl FromRequestParts<AppState> for InternalOnly {
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &AppState) -> Result<Self, Self::Rejection> {
        let provided = parts
            .headers
            .get("x-internal-token")
            .and_then(|value| value.to_str().ok())
            .unwrap_or("");
        let expected = state.config.ai_proveedores_internal_token.as_bytes();
        let provided = provided.as_bytes();
        if provided.ct_eq(expected).into() {
            Ok(Self)
        } else {
            Err(AppError::Unauthorized)
        }
    }
}
