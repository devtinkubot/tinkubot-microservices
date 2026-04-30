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

pub fn is_lid_or_bsuid(value: &str) -> bool {
    let v = value.trim();
    if v.ends_with("@lid") {
        return true;
    }
    let chars: Vec<char> = v.chars().collect();
    if chars.len() >= 4
        && chars[0].is_ascii_uppercase()
        && chars[1].is_ascii_uppercase()
        && chars[2] == '.'
        && chars[3..].iter().all(|c| c.is_ascii_alphanumeric())
    {
        return true;
    }
    false
}

pub fn extract_real_phone_from_jid(value: &str) -> Option<String> {
    let user = value.trim().strip_suffix("@s.whatsapp.net")?;
    let user = user.trim();
    if user.is_empty() || is_lid_or_bsuid(user) {
        return None;
    }
    Some(user.to_string())
}

