use uuid::Uuid;

use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    models::{FlowState, OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.consent.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    process(&mut flow, payload);
    if flow.has_consent {
        let event_payload = build_consent_payload(&flow, payload);
        persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
    } else {
        persist_transition(state, &mut flow, payload, "onboarding_transition").await?;
    }
    Ok(response_for_state(&flow.state, &state.config))
}

fn needs_new_provider_id(id: &str) -> bool {
    id.trim().is_empty() || id.parse::<Uuid>().is_err()
}

pub(crate) fn process(flow: &mut crate::models::FlowState, payload: &WebhookPayload) -> String {
    let current_state = flow.state.clone();
    if flow.has_consent {
        if needs_new_provider_id(&flow.provider_id) {
            flow.provider_id = Uuid::new_v4().to_string();
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

    if payload.selected_option.as_deref() == Some("continue_provider_onboarding") {
        flow.has_consent = true;
        if needs_new_provider_id(&flow.provider_id) {
            flow.provider_id = Uuid::new_v4().to_string();
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

fn build_consent_payload(flow: &FlowState, payload: &WebhookPayload) -> serde_json::Value {
    let exact_response = payload
        .selected_option
        .as_deref()
        .unwrap_or(payload.message.as_str());
    serde_json::json!({
        "checkpoint": flow.state,
        "phone": payload.phone,
        "raw_phone": payload.phone,
        "from_number": payload.from_number,
        "user_id": payload.user_id,
        "account_id": payload.account_id,
        "display_name": payload.display_name,
        "formatted_name": payload.formatted_name,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "real_phone": flow.real_phone,
        "requires_real_phone": flow.real_phone.is_none(),
        "consent_timestamp": payload.timestamp,
        "message_id": payload.id,
        "exact_response": exact_response,
        "platform": "whatsapp"
    })
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
    fn process_accepts_button_tap() {
        let mut flow = FlowState::new(
            "+593959091325".to_string(),
            "test_account_001".to_string(),
            "onboarding_consent".to_string(),
        );
        let payload = make_payload("", Some("continue_provider_onboarding"));

        process(&mut flow, &payload);

        assert!(flow.has_consent);
        assert_eq!(flow.state, "onboarding_real_phone");
        assert!(flow.provider_id.parse::<Uuid>().is_ok());
        assert_ne!(flow.provider_id, "test_account_001");
    }

    #[test]
    fn process_rejects_text_input() {
        let mut flow = FlowState::new(
            "+593959091325".to_string(),
            "test_account_001".to_string(),
            "onboarding_consent".to_string(),
        );
        let payload = make_payload("SI", None);

        process(&mut flow, &payload);

        assert!(!flow.has_consent);
        assert_eq!(flow.state, "onboarding_consent");
    }

    #[test]
    fn process_skips_to_menu_if_already_consented() {
        let mut flow = FlowState::new(
            "+593959091325".to_string(),
            Uuid::new_v4().to_string(),
            "onboarding_consent".to_string(),
        );
        flow.has_consent = true;
        let payload = make_payload("cualquier mensaje", None);

        process(&mut flow, &payload);

        assert_eq!(flow.state, "awaiting_menu_option");
    }
}
