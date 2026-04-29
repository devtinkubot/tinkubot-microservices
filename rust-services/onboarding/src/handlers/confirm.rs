use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    models::{FlowState, OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.review_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    process(&mut flow);

    let event_payload = serde_json::json!({
        "checkpoint": "review_pending_verification",
        "provider_id": flow.provider_id,
        "phone": flow.phone,
        "source": "rust_onboarding",
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
