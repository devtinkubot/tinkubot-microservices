use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition},
    logic::{response_for_state, set_transition_fields},
    normalize::is_affirmative,
    models::{OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.consent.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    let next_state = process(&mut flow, payload);
    persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
    let _ = next_state;
    Ok(response_for_state(&current_state))
}

pub(crate) fn process(flow: &mut crate::models::FlowState, payload: &WebhookPayload) -> String {
    let current_state = flow.state.clone();
    if flow.has_consent {
        if flow.provider_id.trim().is_empty() {
            flow.provider_id = payload.account_id.clone();
            let next = if flow.real_phone.as_deref().unwrap_or("").trim().is_empty() {
                "onboarding_real_phone".to_string()
            } else {
                "onboarding_city".to_string()
            };
            set_transition_fields(flow, &current_state, &next);
            flow.state = next;
            return flow.state.clone();
        }

        set_transition_fields(flow, &current_state, "awaiting_menu_option");
        flow.state = "awaiting_menu_option".to_string();
        return flow.state.clone();
    }

    if is_affirmative(payload.message.as_str(), payload.selected_option.as_deref()) {
        flow.has_consent = true;
        if flow.provider_id.trim().is_empty() {
            flow.provider_id = payload.account_id.clone();
        }
        let next = if flow.real_phone.as_deref().unwrap_or("").trim().is_empty() {
            "onboarding_real_phone".to_string()
        } else {
            "onboarding_city".to_string()
        };
        set_transition_fields(flow, &current_state, &next);
        flow.state = next;
        return flow.state.clone();
    }

    set_transition_fields(flow, &current_state, "onboarding_consent");
    flow.state = "onboarding_consent".to_string();
    flow.state.clone()
}
