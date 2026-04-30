use crate::models::ResponseMessage;

pub(super) fn face_photo() -> ResponseMessage {
    ResponseMessage {
        response: "*Envía tu foto de perfil.*\n\n\
            Que tu rostro se vea claro y que la imagen esté bien iluminada."
            .to_string(),
        ui: None,
    }
}
