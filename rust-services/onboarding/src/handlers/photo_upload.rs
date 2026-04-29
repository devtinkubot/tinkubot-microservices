use crate::{
    errors::AppError,
    flow::{load_or_create_flow, persist_transition_with_payload},
    logic::{response_for_state, set_transition_fields},
    models::{FlowState, OnboardingResponse, WebhookPayload},
    normalize::validate_base64_image,
    AppState,
};

#[derive(Debug, Clone, Copy)]
pub enum PhotoType {
    DniFront,
    Face,
}

impl PhotoType {
    fn event_type(self) -> &'static str {
        match self {
            PhotoType::DniFront => "provider.onboarding.dni_front.persist_requested",
            PhotoType::Face => "provider.onboarding.face.persist_requested",
        }
    }

    fn next_state(self) -> &'static str {
        match self {
            PhotoType::DniFront => "onboarding_face_photo",
            PhotoType::Face => "onboarding_experience",
        }
    }

}

#[tracing::instrument(skip(state, payload), fields(phone = %payload.phone))]
pub async fn handle(
    state: &AppState,
    payload: &WebhookPayload,
    photo_type: PhotoType,
) -> Result<OnboardingResponse, AppError> {
    let mut flow = load_or_create_flow(state, payload).await?;
    let current_state = flow.state.clone();

    let Some(b64) = payload.media_base64.as_deref() else {
        set_transition_fields(&mut flow, &current_state, &current_state);
        state.store.set_flow(&flow).await?;
        return Ok(response_for_state(&flow.state, &state.config));
    };

    validate_base64_image(b64, 5 * 1024 * 1024)?;

    let next = photo_type.next_state();
    set_transition_fields(&mut flow, &current_state, next);
    flow.state = next.to_string();

    let event_payload = build_photo_payload(payload, &flow);
    persist_transition_with_payload(state, &mut flow, payload, photo_type.event_type(), event_payload).await?;
    Ok(response_for_state(&flow.state, &state.config))
}

fn build_photo_payload(payload: &WebhookPayload, flow: &FlowState) -> serde_json::Value {
    serde_json::json!({
        "image_base64": payload.media_base64,
        "content_type": payload.media_mimetype,
        "checkpoint": flow.checkpoint.as_deref().unwrap_or(&flow.state),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn photo_type_transitions_are_correct() {
        assert_eq!(PhotoType::DniFront.next_state(), "onboarding_face_photo");
        assert_eq!(PhotoType::Face.next_state(), "onboarding_experience");
    }

}
