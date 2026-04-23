use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition},
    logic::{response_for_state, set_transition_fields},
    models::{OnboardingResponse, WebhookPayload},
    normalize::validate_base64_image,
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.dni_front.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    let image = match payload.media_base64.as_deref() {
        Some(value) => validate_base64_image(value, 5 * 1024 * 1024)?,
        None => {
            set_transition_fields(&mut flow, &current_state, &current_state);
            persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
            return Ok(response_for_state(&current_state));
        }
    };

    let provider_id = flow.provider_id.trim().to_string();
    let path = format!("providers/{provider_id}/dni_front.{}", image.extension);
    let public_url = state
        .supabase
        .upload_to_storage(&path, &image.bytes, &image.mime_type)
        .await
        .map_err(|_| AppError::BadRequest("No pudimos subir la foto frontal del DNI. Intenta otra vez.".to_string()))?;
    flow.dni_front_url = Some(public_url);
    set_transition_fields(&mut flow, &current_state, "onboarding_face_photo");
    flow.state = "onboarding_face_photo".to_string();
    persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
    Ok(response_for_state(&current_state))
}
