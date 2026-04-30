use crate::{
    config::Config,
    models::{ResponseMessage, UIConfig, UIOption},
};

pub(super) fn social_media(config: &Config) -> ResponseMessage {
    let image_url = config.wa_provider_social_network_image_url.trim().to_string();
    let (header_type, header_media_url, header_text) = if image_url.is_empty() {
        (Some("text".to_string()), None, Some("Redes sociales".to_string()))
    } else {
        (Some("image".to_string()), Some(image_url), None)
    };

    ResponseMessage {
        response: "*Agrega tus redes sociales en una sola línea*\n\n\
            Sigue el ejemplo de la imagen. Puedes escribir Facebook, Instagram o ambas \
            en el orden que prefieras. Si no deseas agregarlas ahora, toca Omitir."
            .to_string(),
        ui: Some(UIConfig {
            ui_type: "buttons".to_string(),
            id: "provider_onboarding_social_media_v1".to_string(),
            options: Some(vec![UIOption {
                id: "skip_onboarding_social_media".to_string(),
                title: "Omitir".to_string(),
                description: None,
            }]),
            header_type,
            header_text,
            header_media_url,
            footer_text: Some("Si no deseas agregarlas ahora, toca Omitir.".to_string()),
            list_button_text: None,
            list_section_title: None,
        }),
    }
}
