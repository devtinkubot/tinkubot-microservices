use crate::models::{ResponseMessage, UIConfig};

pub(super) fn city() -> ResponseMessage {
    ResponseMessage {
        response: "Compartí tu *ubicación* para continuar. Tocá el ícono de \
            ubicación en WhatsApp y enviala."
            .to_string(),
        ui: Some(UIConfig {
            ui_type: "location_request".to_string(),
            id: "onboarding_city_location_request_initial".to_string(),
            options: None,
            header_type: None,
            header_text: None,
            header_media_url: None,
            footer_text: None,
            list_button_text: None,
            list_section_title: None,
        }),
    }
}
