use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    models::{FlowState, OnboardingResponse, WebhookPayload},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.city.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    set_transition_fields(&mut flow, &current_state, &current_state);
    let _ = process(&mut flow, payload);
    let event_payload = build_city_payload(&flow, payload);
    persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
    Ok(response_for_state(&flow.state, &state.config))
}

fn build_city_payload(flow: &FlowState, _payload: &WebhookPayload) -> serde_json::Value {
    serde_json::json!({
        "location_lat": flow.location_lat,
        "location_lng": flow.location_lng,
        "checkpoint": flow.checkpoint.as_deref().unwrap_or(&flow.state),
    })
}

pub(crate) fn process(flow: &mut crate::models::FlowState, payload: &WebhookPayload) -> bool {
    let current_state = flow.state.clone();
    let Some(location) = &payload.location else {
        return false;
    };
    flow.city = None;
    flow.location_lat = Some(location.latitude);
    flow.location_lng = Some(location.longitude);
    set_transition_fields(flow, &current_state, "onboarding_dni_front_photo");
    flow.state = "onboarding_dni_front_photo".to_string();
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::FlowState;

    fn make_payload(message: &str) -> WebhookPayload {
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
            selected_option: None,
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

    fn make_location_payload(lat: f64, lng: f64, name: Option<&str>, address: Option<&str>) -> WebhookPayload {
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
            message: String::new(),
            message_type: None,
            selected_option: None,
            flow_payload: None,
            location: Some(crate::models::LocationPayload {
                latitude: lat,
                longitude: lng,
                name: name.map(|s| s.to_string()),
                address: address.map(|s| s.to_string()),
            }),
            timestamp: "2026-01-01T00:00:00Z".to_string(),
            id: None,
            account_id: "test_account_001".to_string(),
            media_base64: None,
            media_mimetype: None,
            media_filename: None,
        }
    }

    #[test]
    fn process_with_location_with_name_ignores_name() {
        let mut flow = FlowState::new(
            "p".to_string(),
            "a".to_string(),
            "onboarding_city".to_string(),
        );
        let payload = make_location_payload(-0.22985, -78.52495, Some("Centrosur"), None);

        let result = process(&mut flow, &payload);

        assert!(result);
        assert_eq!(flow.city, None);
        assert_eq!(flow.location_lat, Some(-0.22985));
        assert_eq!(flow.location_lng, Some(-78.52495));
        assert_eq!(flow.state, "onboarding_dni_front_photo");
    }

    #[test]
    fn process_with_location_without_name_still_advances() {
        let mut flow = FlowState::new(
            "p".to_string(),
            "a".to_string(),
            "onboarding_city".to_string(),
        );
        let payload = make_location_payload(-2.19616, -79.88621, None, None);

        let result = process(&mut flow, &payload);

        assert!(result);
        assert_eq!(flow.city, None);
        assert_eq!(flow.state, "onboarding_dni_front_photo");
    }

    #[test]
    fn process_text_message_rejected() {
        let mut flow = FlowState::new(
            "p".to_string(),
            "a".to_string(),
            "onboarding_city".to_string(),
        );
        let payload = make_payload("Quito");

        let result = process(&mut flow, &payload);

        assert!(!result);
        assert_eq!(flow.state, "onboarding_city");
    }

    #[test]
    fn process_empty_city_stays_in_state() {
        let mut flow = FlowState::new(
            "p".to_string(),
            "a".to_string(),
            "onboarding_city".to_string(),
        );
        let payload = make_payload("   ");

        let result = process(&mut flow, &payload);

        assert!(!result);
        assert_eq!(flow.state, "onboarding_city");
    }
}
