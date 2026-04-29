use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    models::{FlowState, OnboardingResponse, WebhookPayload},
    normalize::{normalize_text, parse_social_urls},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.social.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    let social = parse_social_urls(payload.message.as_str());
    let skip = matches!(
        normalize_text(payload.message.as_str()).as_str(),
        "omitir" | "na" | "n a" | "ninguno" | "skip" | "saltar"
    );

    if social.facebook_username.is_none() && social.instagram_username.is_none() && !skip {
        set_transition_fields(&mut flow, &current_state, &current_state);
        let event_payload = build_social_payload(&flow);
        persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
        return Ok(response_for_state(&flow.state, &state.config));
    }

    flow.facebook_username = social.facebook_username;
    flow.instagram_username = social.instagram_username;
    set_transition_fields(&mut flow, &current_state, "confirm");
    flow.state = "confirm".to_string();
    let event_payload = build_social_payload(&flow);
    persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
    Ok(response_for_state(&flow.state, &state.config))
}

fn build_social_payload(flow: &FlowState) -> serde_json::Value {
    serde_json::json!({
        "facebook_username": flow.facebook_username,
        "instagram_username": flow.instagram_username,
        "checkpoint": flow.checkpoint.as_deref().unwrap_or(&flow.state),
    })
}
