use crate::{
    errors::AppError,
    handlers,
    flow::load_or_create_flow,
    models::{FlowState, OnboardingResponse, ResponseMessage, WebhookPayload},
    AppState,
};

pub async fn dispatch(state: AppState, payload: WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let flow: FlowState = load_or_create_flow(&state, &payload).await?;

    // Reset de sesión — solo número de prueba 593959091325
    let is_test_phone = payload.phone.contains("593959091325")
        || payload.from_number.as_deref().unwrap_or("").contains("593959091325")
        || flow.real_phone.as_deref() == Some("593959091325");
    let is_reset_cmd = payload.message.trim().eq_ignore_ascii_case("reset");

    if is_test_phone && is_reset_cmd {
        let provider_id = flow.provider_id.clone();
        let is_valid_uuid = !provider_id.is_empty()
            && provider_id != "bot-proveedores"
            && uuid::Uuid::parse_str(&provider_id).is_ok();
        if is_valid_uuid {
            let _ = state.supabase.delete_provider_data(&provider_id).await;
        }
        state.store.delete_flow(&payload.phone).await?;
        return Ok(OnboardingResponse {
            success: true,
            messages: vec![ResponseMessage {
                response: "Sesión reseteada. Enviá *Hola* para comenzar de nuevo.".to_string(),
                ui: None,
            }],
        });
    }

    match flow.state.as_str() {
        "onboarding_consent" => handlers::consent::handle(&state, &payload).await,
        "onboarding_real_phone" => handlers::real_phone::handle(&state, &payload).await,
        "onboarding_city" => handlers::city::handle(&state, &payload).await,
        "onboarding_experience" => handlers::experience::handle(&state, &payload).await,
        "onboarding_add_another_service" => handlers::add_service::handle(&state, &payload).await,
        "onboarding_specialty" => handlers::specialty::handle(&state, &payload).await,
        "onboarding_dni_front_photo" => handlers::dni_front_photo::handle(&state, &payload).await,
        "onboarding_face_photo" => handlers::face_photo::handle(&state, &payload).await,
        "onboarding_social_media" => handlers::social_media::handle(&state, &payload).await,
        "awaiting_menu_option" => handlers::consent::handle(&state, &payload).await,
        "confirm" => handlers::confirm::handle(&state, &payload).await,
        _ => {
            let mut fallback = flow;
            fallback.state = "onboarding_consent".to_string();
            state.store.set_flow(&fallback).await?;
            handlers::consent::handle(&state, &payload).await
        }
    }
}
