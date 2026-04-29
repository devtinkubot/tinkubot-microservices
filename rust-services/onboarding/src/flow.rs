use crate::{
    errors::AppError,
    events::publish_onboarding_event,
    logic::update_updated_at,
    models::{FlowState, WebhookPayload},
    AppState,
};

pub async fn load_or_create_flow(state: &AppState, payload: &WebhookPayload) -> Result<FlowState, AppError> {
    let mut flow = match state.store.get_flow(&payload.phone).await? {
        Some(flow) => flow,
        None => {
            let flow = FlowState::new(
                payload.phone.clone(),
                payload.account_id.clone(),
                "onboarding_consent".to_string(),
            );
            state.store.set_flow(&flow).await?;
            flow
        }
    };

    if flow.account_id.is_empty() {
        flow.account_id = payload.account_id.clone();
    }
    if let Some(ref val) = payload.from_number {
        if flow.from_number.as_deref() != Some(val) {
            flow.from_number = Some(val.clone());
        }
    }
    if let Some(ref val) = payload.user_id {
        if flow.user_id.as_deref() != Some(val) {
            flow.user_id = Some(val.clone());
        }
    }
    if let Some(ref val) = payload.display_name {
        if flow.display_name.as_deref() != Some(val) {
            flow.display_name = Some(val.clone());
        }
    }
    if let Some(ref val) = payload.formatted_name {
        if flow.formatted_name.as_deref() != Some(val) {
            flow.formatted_name = Some(val.clone());
        }
    }
    if let Some(ref val) = payload.first_name {
        if flow.first_name.as_deref() != Some(val) {
            flow.first_name = Some(val.clone());
        }
    }
    if let Some(ref val) = payload.last_name {
        if flow.last_name.as_deref() != Some(val) {
            flow.last_name = Some(val.clone());
        }
    }

    if flow.real_phone.is_none() {
        let candidate = payload
            .from_number
            .as_deref()
            .and_then(crate::normalize::extract_real_phone_from_jid);
        if let Some(phone) = candidate {
            flow.real_phone = Some(phone);
        }
    }

    Ok(flow)
}

pub async fn persist_transition(
    state: &AppState,
    flow: &mut FlowState,
    payload: &WebhookPayload,
    event_type: &str,
) -> Result<(), AppError> {
    let event_payload = serde_json::to_value(payload)?;
    persist_transition_with_payload(state, flow, payload, event_type, event_payload).await
}

pub async fn persist_transition_with_payload(
    state: &AppState,
    flow: &mut FlowState,
    payload: &WebhookPayload,
    event_type: &str,
    event_payload: serde_json::Value,
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
        &event_payload,
    )
    .await?;
    Ok(())
}
