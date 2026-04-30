use crate::{errors::AppError, models::{OnboardingResponse, WebhookPayload}, AppState};

use super::photo_upload::{handle as handle_photo_upload, PhotoType};

pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    handle_photo_upload(state, payload, PhotoType::DniFront).await
}
