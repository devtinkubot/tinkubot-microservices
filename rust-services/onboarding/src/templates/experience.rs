use crate::models::{ResponseMessage, UIConfig, UIOption};

pub(super) fn experience() -> ResponseMessage {
    ResponseMessage {
        response: "Selecciona tus *años de experiencia*.".to_string(),
        ui: Some(UIConfig {
            ui_type: "list".to_string(),
            id: "onboarding_experience_ranges_v1".to_string(),
            options: Some(vec![
                UIOption {
                    id: "onboarding_experience_under_1".to_string(),
                    title: "Menos de 1 año".to_string(),
                    description: Some("Si estás empezando".to_string()),
                },
                UIOption {
                    id: "onboarding_experience_1_3".to_string(),
                    title: "1 a 3 años".to_string(),
                    description: Some("Experiencia inicial".to_string()),
                },
                UIOption {
                    id: "onboarding_experience_3_5".to_string(),
                    title: "3 a 5 años".to_string(),
                    description: Some("Ya trabajas con frecuencia".to_string()),
                },
                UIOption {
                    id: "onboarding_experience_5_10".to_string(),
                    title: "5 a 10 años".to_string(),
                    description: Some("Experiencia sólida".to_string()),
                },
                UIOption {
                    id: "onboarding_experience_10_plus".to_string(),
                    title: "Más de 10 años".to_string(),
                    description: Some("Amplia trayectoria".to_string()),
                },
            ]),
            header_type: Some("text".to_string()),
            header_text: Some("Años de experiencia".to_string()),
            header_media_url: None,
            footer_text: Some("Podrás actualizarlo más adelante si lo necesitas.".to_string()),
            list_button_text: Some("Seleccionar".to_string()),
            list_section_title: Some("Elige un rango".to_string()),
        }),
    }
}
