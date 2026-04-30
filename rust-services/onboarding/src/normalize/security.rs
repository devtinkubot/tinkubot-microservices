use url::Url;

use crate::errors::AppError;

#[allow(dead_code)]
pub fn validate_url(raw: &str) -> Result<String, AppError> {
    let parsed = Url::parse(raw)
        .or_else(|_| Url::parse(&format!("https://{raw}")))
        .map_err(|_| AppError::BadRequest("URL inválida".to_string()))?;

    if parsed.scheme() != "https" {
        return Err(AppError::BadRequest(
            "solo se permiten URLs HTTPS".to_string(),
        ));
    }

    let host = parsed.host_str().unwrap_or("");
    if host == "localhost"
        || host.ends_with(".localhost")
        || host
            .parse::<std::net::IpAddr>()
            .map(|ip| match ip {
                std::net::IpAddr::V4(v4) => v4.is_private() || v4.is_loopback() || v4.is_link_local(),
                std::net::IpAddr::V6(v6) => v6.is_loopback(),
            })
            .unwrap_or(false)
    {
        return Err(AppError::BadRequest("host no permitido".to_string()));
    }

    Ok(parsed.to_string())
}

#[cfg(test)]
mod tests {
    use super::validate_url;

    #[test]
    fn validate_url_blocks_non_https() {
        assert!(validate_url("http://instagram.com/user").is_err());
        assert!(validate_url("javascript:alert(1)").is_err());
        assert!(validate_url("file:///etc/passwd").is_err());
    }

    #[test]
    fn validate_url_blocks_internal_hosts() {
        assert!(validate_url("https://localhost/admin").is_err());
        assert!(validate_url("https://192.168.1.1/").is_err());
    }

    #[test]
    fn validate_url_accepts_valid_https() {
        assert!(validate_url("https://instagram.com/username").is_ok());
        assert!(validate_url("instagram.com/username").is_ok());
    }
}
