use crate::models::ResponseMessage;

pub(super) fn specialty() -> ResponseMessage {
    ResponseMessage {
        response: "*Describe el servicio que ofreces*\n\n\
            Escribe solo un servicio por mensaje. \
            Mientras más claro y detallado sea, mejor podremos clasificarlo."
            .to_string(),
        ui: None,
    }
}
