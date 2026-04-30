use crate::models::ResponseMessage;

pub(super) fn dni_front_photo() -> ResponseMessage {
    ResponseMessage {
        response: "*Envía una foto frontal de tu cédula.*\n\n\
            Asegúrate de que tus datos y la imagen sean claros."
            .to_string(),
        ui: None,
    }
}
