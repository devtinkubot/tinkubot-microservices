use base64::{engine::general_purpose::STANDARD, Engine as _};
use crate::errors::AppError;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedImage {
    pub bytes: Vec<u8>,
    pub mime_type: String,
    pub extension: String,
}

pub fn validate_base64_image(input: &str, max_bytes: usize) -> Result<ValidatedImage, AppError> {
    let raw = input.trim();
    if raw.is_empty() {
        return Err(AppError::BadRequest("missing image data".to_string()));
    }

    let payload = raw
        .split_once(',')
        .map(|(_, data)| data)
        .unwrap_or(raw)
        .trim();
    let decoded = STANDARD
        .decode(payload)
        .map_err(|_| AppError::BadRequest("invalid base64 image".to_string()))?;
    if decoded.len() > max_bytes {
        return Err(AppError::BadRequest(
            "image too large. maximum 5MB".to_string(),
        ));
    }

    let (mime_type, extension) = detect_image_format(&decoded)
        .ok_or_else(|| AppError::BadRequest("invalid image format. use PNG or JPG".to_string()))?;
    image::load_from_memory(&decoded)
        .map_err(|_| AppError::BadRequest("imagen corrupta o no soportada".to_string()))?;

    Ok(ValidatedImage {
        bytes: decoded,
        mime_type: mime_type.to_string(),
        extension: extension.to_string(),
    })
}

fn detect_image_format(bytes: &[u8]) -> Option<(&'static str, &'static str)> {
    let kind = infer::get(bytes)?;
    match kind.mime_type() {
        "image/png" => Some(("image/png", "png")),
        "image/jpeg" => Some(("image/jpeg", "jpg")),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::validate_base64_image;

    #[test]
    fn validates_png_base64() {
        use base64::engine::general_purpose::STANDARD;
        use base64::Engine as _;
        use image::{ImageFormat, Rgba, RgbaImage};
        use std::io::Cursor;

        let mut buffer = Vec::new();
        let png = RgbaImage::from_pixel(1, 1, Rgba([255, 0, 0, 255]));
        png.write_to(&mut Cursor::new(&mut buffer), ImageFormat::Png)
            .expect("png");

        let data = STANDARD.encode(&buffer);
        let image = validate_base64_image(&data, 5 * 1024 * 1024).expect("image");
        assert_eq!(image.mime_type, "image/png");
        assert_eq!(image.extension, "png");
    }

    #[test]
    fn rejects_polyglot_png_header_with_garbage_body() {
        use base64::engine::general_purpose::STANDARD;
        use base64::Engine as _;

        let mut fake: Vec<u8> = b"\x89PNG\r\n\x1a\n".to_vec();
        fake.extend_from_slice(b"not a real png body at all");
        let b64 = STANDARD.encode(&fake);
        let result = validate_base64_image(&b64, 5 * 1024 * 1024);
        assert!(result.is_err(), "debe rechazar polyglot file");
    }

    #[test]
    fn rejects_jpeg_header_with_garbage_body() {
        use base64::engine::general_purpose::STANDARD;
        use base64::Engine as _;

        let mut fake: Vec<u8> = b"\xff\xd8\xff".to_vec();
        fake.extend_from_slice(b"not a real jpeg body");
        let b64 = STANDARD.encode(&fake);
        let result = validate_base64_image(&b64, 5 * 1024 * 1024);
        assert!(result.is_err(), "debe rechazar jpeg falso");
    }
}
