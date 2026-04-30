use crate::models::ResponseMessage;

pub(super) fn real_phone() -> ResponseMessage {
    ResponseMessage {
        response: "*Para continuar, escribe tu número de celular.*".to_string(),
        ui: None,
    }
}
