use chrono::Utc;

use crate::models::{FlowState, OnboardingResponse};

pub fn response_for_state(state: &str) -> OnboardingResponse {
    OnboardingResponse::single(state)
}

pub fn set_transition_fields(flow: &mut FlowState, current_state: &str, next_state: &str) {
    flow.step = Some(current_state.to_string());
    flow.checkpoint = Some(next_state.to_string());
}

pub fn update_updated_at(flow: &mut FlowState) {
    flow.updated_at = Some(Utc::now().to_rfc3339());
}
