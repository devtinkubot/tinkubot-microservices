use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition},
    logic::{response_for_state, set_transition_fields},
    normalize::{is_affirmative, is_negative},
    models::{OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.add_another_service.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    let _ = process(&mut flow, payload);
    persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
    Ok(response_for_state(&current_state))
}

pub(crate) fn process(flow: &mut crate::models::FlowState, payload: &WebhookPayload) -> Option<bool> {
    let current_state = flow.state.clone();
    let text = payload.message.as_str();
    let selected = payload.selected_option.as_deref();
    if is_affirmative(text, selected) {
        set_transition_fields(flow, &current_state, "onboarding_specialty");
        flow.state = "onboarding_specialty".to_string();
        return Some(true);
    }
    if is_negative(text, selected) {
        set_transition_fields(flow, &current_state, "confirm");
        flow.state = "confirm".to_string();
        return Some(false);
    }
    None
}
