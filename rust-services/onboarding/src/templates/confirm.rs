use crate::models::ResponseMessage;

pub(super) fn confirm_done() -> ResponseMessage {
    ResponseMessage {
        response: "✅ Gracias. Registramos tu información y la revisaremos antes de activar tu perfil."
            .to_string(),
        ui: None,
    }
}
