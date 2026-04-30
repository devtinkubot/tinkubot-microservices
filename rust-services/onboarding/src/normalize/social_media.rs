use url::Url;

use super::text::normalize_text;

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SocialMediaLinks {
    pub facebook_username: Option<String>,
    pub instagram_username: Option<String>,
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
        let candidate = tail
            .trim_start_matches([':', '=', '-', ' ', '/', '\t'])
            .split_whitespace()
            .next()
            .unwrap_or(tail);
        return clean_social_username(candidate);
    }

    if platform == "instagram" && text.trim_start().starts_with('@') {
        return clean_social_username(text);
    }

    None
}

fn extract_username_from_url(text: &str, platform: &str) -> Option<String> {
    let lower = text.to_lowercase();
    let host_candidates: &[&str] = match platform {
        "facebook" => &["facebook.com", "fb.com"],
        "instagram" => &["instagram.com", "instagr.am"],
        _ => return None,
    };

    let start = host_candidates
        .iter()
        .filter_map(|host| lower.find(host))
        .min()?;
    let slice = text[start..]
        .split_whitespace()
        .next()
        .unwrap_or(&text[start..]);

    let normalized = if slice.contains("://") {
        slice.to_string()
    } else {
        format!("https://{slice}")
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
    use super::parse_social_urls;

    #[test]
    fn parses_social_links() {
        let links = parse_social_urls("instagram: @mi_negocio facebook.com/mi.negocio");
        assert_eq!(links.instagram_username.as_deref(), Some("mi_negocio"));
        assert_eq!(links.facebook_username.as_deref(), Some("mi.negocio"));
    }
}
