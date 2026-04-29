use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    models::{FlowState, OnboardingResponse, WebhookPayload},
    normalize::normalize_text,
    AppState,
};

const EVENT_TYPE: &str = "provider.onboarding.services.persist_requested";

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(state: &AppState, payload: &WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();
    let query = normalize_text(payload.message.as_str());
    if query.is_empty() {
        set_transition_fields(&mut flow, &current_state, &current_state);
        let event_payload = build_specialty_payload(&flow, payload);
        persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
        return Ok(response_for_state(&flow.state, &state.config));
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
    set_transition_fields(&mut flow, &current_state, "onboarding_add_another_service");
    flow.state = "onboarding_add_another_service".to_string();
    let event_payload = build_specialty_payload(&flow, payload);
    persist_transition_with_payload(state, &mut flow, payload, EVENT_TYPE, event_payload).await?;
    Ok(response_for_state(&flow.state, &state.config))
}

fn build_specialty_payload(flow: &FlowState, payload: &WebhookPayload) -> serde_json::Value {
    serde_json::json!({
        "raw_service_text": payload.message,
        "service_position": flow.services.len().saturating_sub(1),
        "checkpoint": flow.checkpoint.as_deref().unwrap_or(&flow.state),
    })
}
