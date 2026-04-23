use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition},
    logic::{response_for_state, set_transition_fields},
    models::{OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.confirm.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    process(&mut flow);
    persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
    Ok(response_for_state(&current_state))
}

pub(crate) fn process(flow: &mut crate::models::FlowState) {
    let current_state = flow.state.clone();
    flow.onboarding_complete = true;
    set_transition_fields(flow, &current_state, "completed");
    flow.state = "completed".to_string();
}
