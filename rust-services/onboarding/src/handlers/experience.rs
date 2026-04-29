use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    normalize::normalize_experience,
    models::{FlowState, OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.experience.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    let _ = process(&mut flow, payload);
    let event_payload = build_experience_payload(&flow);
    persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
    Ok(response_for_state(&flow.state, &state.config))
}

fn build_experience_payload(flow: &FlowState) -> serde_json::Value {
    serde_json::json!({
        "experience_range": flow.experience_range,
        "checkpoint": flow.checkpoint.as_deref().unwrap_or(&flow.state),
    })
}

pub(crate) fn process(flow: &mut FlowState, payload: &WebhookPayload) -> bool {
    let current_state = flow.state.clone();
    match normalize_experience(payload.message.as_str(), payload.selected_option.as_deref()) {
        Some(experience_range) => {
            flow.experience_range = Some(experience_range);
            set_transition_fields(flow, &current_state, "onboarding_specialty");
            flow.state = "onboarding_specialty".to_string();
            true
        }
        None => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::FlowState;

    fn make_payload(message: &str, selected: Option<&str>) -> WebhookPayload {
        WebhookPayload {
            phone: "+593959091325".to_string(),
            from_number: None,
            user_id: None,
            display_name: None,
            formatted_name: None,
            first_name: None,
            last_name: None,
            username: None,
            country_code: None,
            context_from: None,
            context_id: None,
            content: None,
            message: message.to_string(),
            message_type: None,
            selected_option: selected.map(str::to_string),
            flow_payload: None,
            location: None,
            timestamp: "2026-01-01T00:00:00Z".to_string(),
            id: None,
            account_id: "test_account_001".to_string(),
            media_base64: None,
            media_mimetype: None,
            media_filename: None,
        }
    }

    #[test]
    fn process_list_selection_transitions_to_specialty() {
        let mut flow = FlowState::new(
            "p".to_string(),
            "a".to_string(),
            "onboarding_experience".to_string(),
        );
        let payload = make_payload("", Some("onboarding_experience_1_3"));

        let result = process(&mut flow, &payload);

        assert!(result);
        assert_eq!(flow.experience_range.as_deref(), Some("1 a 3 años"));
        assert_eq!(flow.state, "onboarding_specialty");
    }

    #[test]
    fn process_unknown_selection_stays_in_state() {
        let mut flow = FlowState::new(
            "p".to_string(),
            "a".to_string(),
            "onboarding_experience".to_string(),
        );
        let payload = make_payload("texto libre sin selección", None);

        let result = process(&mut flow, &payload);

        assert!(result);
        assert_eq!(flow.state, "onboarding_specialty");
        assert_eq!(flow.experience_range.as_deref(), Some("texto libre sin selección"));
    }
}
