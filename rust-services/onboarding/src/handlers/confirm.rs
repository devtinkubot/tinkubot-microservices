use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    models::{FlowState, OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.registration.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    process(&mut flow);

    let provider_data = serde_json::json!({
        "phone": flow.phone,
        "account_id": flow.account_id,
        "from_number": flow.from_number,
        "user_id": flow.user_id,
        "real_phone": flow.real_phone,
        "display_name": flow.display_name,
        "formatted_name": flow.formatted_name,
        "first_name": flow.first_name,
        "last_name": flow.last_name,
        "city": flow.city,
        "location_lat": flow.location_lat,
        "location_lng": flow.location_lng,
        "experience_range": flow.experience_range,
        "services_list": flow.services,
        "facebook_username": flow.facebook_username,
        "instagram_username": flow.instagram_username,
        "has_consent": flow.has_consent,
        "onboarding_complete": flow.onboarding_complete,
    });

    let flow_snapshot = serde_json::json!({
        "phone": flow.phone,
        "provider_id": flow.provider_id,
        "state": flow.state,
        "checkpoint": flow.checkpoint,
        "step": flow.step,
        "has_consent": flow.has_consent,
        "real_phone": flow.real_phone,
        "account_id": flow.account_id,
        "from_number": flow.from_number,
        "user_id": flow.user_id,
        "display_name": flow.display_name,
        "formatted_name": flow.formatted_name,
        "first_name": flow.first_name,
        "last_name": flow.last_name,
        "city": flow.city,
        "location_lat": flow.location_lat,
        "location_lng": flow.location_lng,
        "experience_range": flow.experience_range,
        "services": flow.services,
        "specialty": flow.specialty,
        "facebook_username": flow.facebook_username,
        "instagram_username": flow.instagram_username,
        "onboarding_complete": flow.onboarding_complete,
        "service_slot": flow.service_slot,
    });

    let event_payload = serde_json::json!({
        "checkpoint": "review_pending_verification",
        "provider_data": provider_data,
        "flow": flow_snapshot,
    });
    persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
    Ok(response_for_state(&flow.state, &state.config))
}

pub(crate) fn process(flow: &mut FlowState) {
    let current_state = flow.state.clone();
    flow.onboarding_complete = true;
    set_transition_fields(flow, &current_state, "completed");
    flow.state = "completed".to_string();
}
