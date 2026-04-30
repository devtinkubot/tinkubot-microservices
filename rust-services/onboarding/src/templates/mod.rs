mod add_service;
mod city;
mod confirm;
mod consent;
mod dni_front;
mod experience;
mod face_photo;
mod real_phone;
mod social_media;
mod specialty;

use crate::{
    config::Config,
    models::ResponseMessage,
};

pub fn message_for_state(state: &str, config: &Config) -> ResponseMessage {
    match state {
        "onboarding_consent" => consent::consent(config),
        "onboarding_real_phone" => real_phone::real_phone(),
        "onboarding_city" => city::city(),
        "onboarding_experience" => experience::experience(),
        "onboarding_add_another_service" => add_service::add_another_service(),
        "onboarding_specialty" => specialty::specialty(),
        "onboarding_dni_front_photo" => dni_front::dni_front_photo(),
        "onboarding_face_photo" => face_photo::face_photo(),
        "onboarding_social_media" => social_media::social_media(config),
        "confirm" | "completed" | "awaiting_menu_option" => confirm::confirm_done(),
        _ => ResponseMessage { response: state.to_string(), ui: None },
    }
}
