use super::text::normalize_text;

pub fn normalize_experience(text: &str, selected_option: Option<&str>) -> Option<String> {
    let selected = normalize_text(selected_option.unwrap_or_default());
    let mapped = match selected.as_str() {
        "onboarding_experience_under_1" | "provider_experience_under_1" => Some("Menos de 1 año"),
        "onboarding_experience_1_3" | "provider_experience_1_3" => Some("1 a 3 años"),
        "onboarding_experience_3_5" | "provider_experience_3_5" => Some("3 a 5 años"),
        "onboarding_experience_5_10" | "provider_experience_5_10" => Some("5 a 10 años"),
        "onboarding_experience_10_plus" | "provider_experience_10_plus" => Some("Más de 10 años"),
        _ => None,
    };
    mapped.map(str::to_string).or_else(|| {
        let normalized = text.trim();
        (!normalized.is_empty()).then(|| normalized.to_string())
    })
}
