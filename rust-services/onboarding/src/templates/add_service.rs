use crate::models::{ResponseMessage, UIConfig, UIOption};

pub(super) fn add_another_service() -> ResponseMessage {
    ResponseMessage {
        response: "Presiona *Sí* para agregarlo. Presiona *No* para continuar con el registro."
            .to_string(),
        ui: Some(UIConfig {
            ui_type: "buttons".to_string(),
            id: "provider_onboarding_service_continue_v1".to_string(),
            options: Some(vec![
                UIOption {
                    id: "onboarding_add_another_service_yes".to_string(),
                    title: "Sí".to_string(),
                    description: None,
                },
                UIOption {
                    id: "onboarding_add_another_service_no".to_string(),
                    title: "No".to_string(),
                    description: None,
                },
            ]),
            header_type: Some("text".to_string()),
            header_text: Some("¿Quieres agregar otro servicio?".to_string()),
            header_media_url: None,
            footer_text: None,
            list_button_text: None,
            list_section_title: None,
        }),
    }
}
