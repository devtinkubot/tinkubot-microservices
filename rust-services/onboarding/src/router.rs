use crate::{
    errors::AppError,
    handlers,
    flow::load_or_create_flow,
    models::{OnboardingResponse, WebhookPayload},
    AppState,
};

pub async fn dispatch(state: AppState, payload: WebhookPayload) -> Result<OnboardingResponse, AppError> {
    let flow = load_or_create_flow(&state, &payload).await?;

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
