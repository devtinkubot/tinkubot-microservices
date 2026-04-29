use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    models::{OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.registration.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    process(&mut flow);
    let event_payload = serde_json::json!({
        "checkpoint": flow.checkpoint.as_deref().unwrap_or(&flow.state),
        "phone": flow.phone,
        "real_phone": flow.real_phone,
        "has_consent": flow.has_consent,
        "city": flow.city,
        "location_lat": flow.location_lat,
        "location_lng": flow.location_lng,
        "experience_range": flow.experience_range,
        "specialty": flow.specialty,
        "services": flow.services,
        "facebook_username": flow.facebook_username,
        "instagram_username": flow.instagram_username,
        "onboarding_complete": flow.onboarding_complete,
    });
    persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
    Ok(response_for_state(&flow.state, &state.config))
}

pub(crate) fn process(flow: &mut crate::models::FlowState) {
    let current_state = flow.state.clone();
    flow.onboarding_complete = true;
    set_transition_fields(flow, &current_state, "completed");
    flow.state = "completed".to_string();
}
