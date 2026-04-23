use base64::{engine::general_purpose::STANDARD, Engine as _};
use url::Url;

use crate::errors::AppError;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedImage {
    pub bytes: Vec<u8>,
    pub mime_type: String,
    pub extension: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SocialMediaLinks {
    pub facebook_username: Option<String>,
    pub instagram_username: Option<String>,
}

pub fn normalize_text(value: &str) -> String {
    let mut output = String::with_capacity(value.len());
    for ch in value.trim().chars() {
        let ch = match ch {
            'á' | 'à' | 'ä' | 'â' | 'Á' | 'À' | 'Ä' | 'Â' => 'a',
            'é' | 'è' | 'ë' | 'ê' | 'É' | 'È' | 'Ë' | 'Ê' => 'e',
            'í' | 'ì' | 'ï' | 'î' | 'Í' | 'Ì' | 'Ï' | 'Î' => 'i',
            'ó' | 'ò' | 'ö' | 'ô' | 'Ó' | 'Ò' | 'Ö' | 'Ô' => 'o',
            'ú' | 'ù' | 'ü' | 'û' | 'Ú' | 'Ù' | 'Ü' | 'Û' => 'u',
            'ñ' | 'Ñ' => 'n',
            '.' | ',' | ';' | ':' | '!' | '¡' | '¿' | '?' => ' ',
            _ => ch,
        };
        if ch.is_whitespace() {
            if !output.ends_with(' ') {
                output.push(' ');
            }
        } else {
            output.push(ch.to_ascii_lowercase());
        }
    }
    output.trim().to_string()
}

pub fn is_affirmative(text: &str, selected_option: Option<&str>) -> bool {
    let normalized_option = normalize_text(selected_option.unwrap_or_default());
    if matches!(
        normalized_option.as_str(),
        "1" | "si" | "s" | "yes" | "y" | "acepto" | "autorizo" | "confirmo" | "claro"
            | "de acuerdo" | "continue" | "continuar" | "continue_provider_onboarding"
            | "continue_onboarding"
    ) {
        return true;
    }

    let normalized_text = normalize_text(text);
    matches!(
        normalized_text.as_str(),
        "1" | "si" | "s" | "yes" | "y" | "acepto" | "autorizo" | "confirmo" | "claro"
            | "de acuerdo" | "continuar" | "continue"
    ) || normalized_text.starts_with("si ")
        || normalized_text.starts_with("yes ")
        || normalized_text.contains("acepto")
}

pub fn is_negative(text: &str, selected_option: Option<&str>) -> bool {
    let normalized_option = normalize_text(selected_option.unwrap_or_default());
    if matches!(normalized_option.as_str(), "2" | "no" | "n" | "reject" | "rechazar" | "cancelar") {
        return true;
    }

    let normalized_text = normalize_text(text);
    matches!(
        normalized_text.as_str(),
        "2" | "no" | "n" | "reject" | "rechazar" | "cancelar" | "terminar" | "listo"
    ) || normalized_text.starts_with("no ")
}

pub fn normalize_ecuador_phone(text: &str) -> Option<String> {
    let compact: String = text
        .trim()
        .chars()
        .filter(|ch| !matches!(ch, ' ' | '-' | '(' | ')' | '.' | '\t' | '\n' | '\r'))
        .collect();
    if compact.is_empty() {
        return None;
    }

    let digits = compact.strip_prefix('+').unwrap_or(&compact);
    if !digits.chars().all(|ch| ch.is_ascii_digit()) {
        return None;
    }

    if let Some(rest) = digits.strip_prefix("593") {
        if rest.len() == 9 {
            return Some(format!("593{rest}"));
        }
    }

    None
}

pub fn normalize_city(text: &str) -> Option<String> {
    let normalized = normalize_text(text);
    if normalized.is_empty() {
        None
    } else {
        Some(normalized)
    }
}

pub fn normalize_experience(text: &str, selected_option: Option<&str>) -> Option<String> {
    let selected = normalize_text(selected_option.unwrap_or_default());
    let mapped = match selected.as_str() {
        "onboarding_experience_under_1" | "provider_experience_under_1" => Some("menos de 1 año"),
        "onboarding_experience_1_3" | "provider_experience_1_3" => Some("1 a 3 años"),
        "onboarding_experience_3_5" | "provider_experience_3_5" => Some("3 a 5 años"),
        "onboarding_experience_5_10" | "provider_experience_5_10" => Some("5 a 10 años"),
        "onboarding_experience_10_plus" | "provider_experience_10_plus" => Some("más de 10 años"),
        _ => None,
    };
    mapped.map(str::to_string).or_else(|| {
        let normalized = text.trim();
        (!normalized.is_empty()).then(|| normalized.to_string())
    })
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

    Ok(ValidatedImage {
        bytes: decoded,
        mime_type: mime_type.to_string(),
        extension: extension.to_string(),
    })
}

fn detect_image_format(bytes: &[u8]) -> Option<(&'static str, &'static str)> {
    if bytes.starts_with(b"\x89PNG\r\n\x1a\n") {
        return Some(("image/png", "png"));
    }
    if bytes.starts_with(b"\xff\xd8\xff") {
        return Some(("image/jpeg", "jpg"));
    }
    None
}

pub fn parse_social_urls(text: &str) -> SocialMediaLinks {
    let raw = text.trim();
    if raw.is_empty() {
        return SocialMediaLinks::default();
    }

    let normalized = normalize_text(raw);
    if normalized.is_empty() || matches!(normalized.as_str(), "omitir" | "na" | "n a" | "ninguno") {
        return SocialMediaLinks::default();
    }

    SocialMediaLinks {
        facebook_username: extract_social_username(raw, "facebook"),
        instagram_username: extract_social_username(raw, "instagram"),
    }
}

fn extract_social_username(text: &str, platform: &str) -> Option<String> {
    let lower = text.to_lowercase();
    let has_platform = lower.contains(platform);
    let has_host = match platform {
        "facebook" => lower.contains("facebook.com") || lower.contains("fb.com"),
        "instagram" => lower.contains("instagram.com") || lower.contains("instagr.am"),
        _ => false,
    };

    if !has_platform && !has_host && !(platform == "instagram" && text.trim_start().starts_with('@')) {
        return None;
    }

    if has_host {
        return extract_username_from_url(text, platform);
    }

    if let Some((_, tail)) = lower.split_once(platform) {
        return clean_social_username(tail);
    }

    if platform == "instagram" && text.trim_start().starts_with('@') {
        return clean_social_username(text);
    }

    None
}

fn extract_username_from_url(text: &str, platform: &str) -> Option<String> {
    let normalized = if text.contains("://") {
        text.to_string()
    } else {
        format!("https://{text}")
    };

    let url = Url::parse(&normalized).ok()?;
    let segments: Vec<_> = url.path_segments()?.filter(|segment| !segment.is_empty()).collect();

    if platform == "facebook" {
        if segments.first().copied() == Some("profile.php") {
            return url
                .query_pairs()
                .find(|(key, _)| key == "id")
                .and_then(|(_, value)| clean_social_username(value.as_ref()));
        }
        return segments.first().and_then(|value| clean_social_username(value));
    }

    segments.first().and_then(|value| clean_social_username(value))
}

fn clean_social_username(value: impl AsRef<str>) -> Option<String> {
    let text = value.as_ref().trim();
    if text.is_empty() {
        return None;
    }

    let trimmed = text
        .trim_start_matches([':', '=', '-', ' ', '/', '\t'])
        .trim_end_matches(['/', '?', '&', ' ', '\t']);
    let cleaned = trimmed.strip_prefix('@').unwrap_or(trimmed).trim();
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validates_png_base64() {
        let data = "iVBORw0KGgo=";
        let image = validate_base64_image(data, 5 * 1024 * 1024).expect("image");
        assert_eq!(image.mime_type, "image/png");
        assert_eq!(image.extension, "png");
    }

    #[test]
    fn parses_social_links() {
        let links = parse_social_urls("instagram: @mi_negocio facebook.com/mi.negocio");
        assert_eq!(links.instagram_username.as_deref(), Some("mi_negocio"));
        assert_eq!(links.facebook_username.as_deref(), Some("mi.negocio"));
    }
}
