use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition},
    logic::{response_for_state, set_transition_fields},
    normalize::normalize_experience,
    models::{OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.experience.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    let _ = process(&mut flow, payload);
    persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
    Ok(response_for_state(&current_state))
}

pub(crate) fn process(flow: &mut crate::models::FlowState, payload: &WebhookPayload) -> bool {
    let current_state = flow.state.clone();
    match normalize_experience(payload.message.as_str(), payload.selected_option.as_deref()) {
        Some(experience_range) => {
            flow.experience_range = Some(experience_range);
            set_transition_fields(flow, &current_state, "onboarding_add_another_service");
            flow.state = "onboarding_add_another_service".to_string();
            true
        }
        None => false,
    }
}
