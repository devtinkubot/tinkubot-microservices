use crate::{
    config::Config,
    models::{ResponseMessage, UIConfig, UIOption},
};

pub(super) fn consent(config: &Config) -> ResponseMessage {
    let text = "Para continuar con tu registro, nos autorizas usar los siguientes datos:\n\n\
        - Foto de ID\n\
        - Foto de Perfil\n\
        - Ubicación\n\n\
        Revisa la política de privacidad aquí: *www.tinku.bot/privacy*"
        .to_string();

    let image_url = config.wa_provider_onboarding_consent_url.trim().to_string();
    let has_image = !image_url.is_empty();

    ResponseMessage {
        response: text,
        ui: Some(UIConfig {
            ui_type: "buttons".to_string(),
            id: "provider_onboarding_continue_v1".to_string(),
            options: Some(vec![UIOption {
                id: "continue_provider_onboarding".to_string(),
                title: "Aceptar".to_string(),
                description: None,
            }]),
            header_type: Some(if has_image { "image" } else { "text" }.to_string()),
            header_text: if has_image { None } else { Some("Registro de proveedor".to_string()) },
            header_media_url: if has_image { Some(image_url) } else { None },
            footer_text: Some("Proceso de validación de proveedor".to_string()),
            list_button_text: None,
            list_section_title: None,
        }),
    }
}
