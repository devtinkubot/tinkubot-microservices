use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition},
    logic::{response_for_state, set_transition_fields},
    models::{OnboardingResponse, WebhookPayload},
    normalize::{normalize_text, parse_social_urls},
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.social_media.persist_requested";

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
        persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
        return Ok(response_for_state(&current_state));
    }

    flow.facebook_username = social.facebook_username;
    flow.instagram_username = social.instagram_username;
    set_transition_fields(&mut flow, &current_state, "confirm");
    flow.state = "confirm".to_string();
    persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
    Ok(response_for_state(&current_state))
}
