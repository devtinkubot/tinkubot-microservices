use crate::{
    errors::AppError,
    events::publish_onboarding_event,
    logic::update_updated_at,
    models::{FlowState, WebhookPayload},
    AppState,
};

pub async fn load_or_create_flow(state: &AppState, payload: &WebhookPayload) -> Result<FlowState, AppError> {
    match state.store.get_flow(&payload.phone).await? {
        Some(flow) => Ok(flow),
        None => {
            let flow = FlowState::new(
                payload.phone.clone(),
                payload.account_id.clone(),
                "onboarding_consent".to_string(),
            );
            state.store.set_flow(&flow).await?;
            Ok(flow)
        }
    }
}

pub async fn persist_transition(
    state: &AppState,
    flow: &mut FlowState,
    payload: &WebhookPayload,
    event_type: &str,
) -> Result<(), AppError> {
    update_updated_at(flow);
    state.store.set_flow(flow).await?;
    let source_message_id = payload.id.as_deref().unwrap_or("");
    let step = flow.step.as_deref().unwrap_or(&flow.state);
    let checkpoint = flow.checkpoint.as_deref().unwrap_or(&flow.state);
    let _ = publish_onboarding_event(
        &state.store.pool,
        &state.config.provider_onboarding_stream_key,
        state.config.provider_onboarding_stream_maxlen,
        event_type,
        &flow.provider_id,
        &flow.phone,
        step,
        checkpoint,
        source_message_id,
        payload,
    )
    .await?;
    Ok(())
}
