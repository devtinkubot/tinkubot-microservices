use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    normalize::normalize_ecuador_phone,
    models::{OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.real_phone.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    let _ = process(&mut flow, payload);
    let event_payload = serde_json::json!({
        "real_phone": flow.real_phone,
        "checkpoint": flow.checkpoint.as_deref().unwrap_or(&flow.state),
    });
    persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
    Ok(response_for_state(&flow.state, &state.config))
}

pub(crate) fn process(flow: &mut crate::models::FlowState, payload: &WebhookPayload) -> bool {
    let current_state = flow.state.clone();
    let phone = normalize_ecuador_phone(payload.message.as_str()).or_else(|| {
        payload
            .selected_option
            .as_deref()
            .and_then(normalize_ecuador_phone)
    });

    match phone {
        Some(phone) => {
            flow.real_phone = Some(phone);
            set_transition_fields(flow, &current_state, "onboarding_city");
            flow.state = "onboarding_city".to_string();
            true
        }
        None => false,
    }
}
