use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition},
    logic::{response_for_state, set_transition_fields},
    models::{OnboardingResponse, WebhookPayload},
    normalize::normalize_text,
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.specialty.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    let query = normalize_text(payload.message.as_str());
    if query.is_empty() {
        set_transition_fields(&mut flow, &current_state, &current_state);
        persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
        return Ok(response_for_state(&current_state));
    }

    let embedding = state
        .openai
        .get_embedding(&query)
        .await
        .map_err(|_| AppError::BadRequest("No pudimos clasificar tu especialidad. Intenta otra vez.".to_string()))?;
    let mut services = state
        .supabase
        .search_similar_services(&embedding, 0.50, 5)
        .await
        .map_err(|_| AppError::BadRequest("No pudimos buscar servicios sugeridos. Intenta otra vez.".to_string()))?;
    if services.is_empty() {
        services.push(query);
    }
    for service in services {
        if !flow.services.iter().any(|item| item == &service) {
            flow.services.push(service);
        }
    }
    flow.specialty = Some(flow.services.join(", "));
    set_transition_fields(&mut flow, &current_state, "onboarding_dni_front_photo");
    flow.state = "onboarding_dni_front_photo".to_string();
    persist_transition(state, &mut flow, payload, EVENT_TYPE).await?;
    Ok(response_for_state(&current_state))
}
