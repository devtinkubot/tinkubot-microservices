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
            | "continue_onboarding" | "onboarding_add_another_service_yes"
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
    if matches!(normalized_option.as_str(), "2" | "no" | "n" | "reject" | "rechazar" | "cancelar" | "onboarding_add_another_service_no") {
        return true;
    }

    let normalized_text = normalize_text(text);
    matches!(
        normalized_text.as_str(),
        "2" | "no" | "n" | "reject" | "rechazar" | "cancelar" | "terminar" | "listo"
    ) || normalized_text.starts_with("no ")
}

