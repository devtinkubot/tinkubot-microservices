use reqwest::Client;
use serde_json::json;

use crate::errors::AppError;

#[derive(Clone)]
pub struct SupabaseClient {
    pub url: String,
    pub key: String,
    pub bucket: String,
    pub client: Client,
}

impl SupabaseClient {
    pub fn new(url: String, key: String, bucket: String) -> Self {
        Self {
            url,
            key,
            bucket,
            client: Client::new(),
        }
    }

    pub async fn search_similar_services(
        &self,
        embedding: &[f32],
        threshold: f32,
        count: i32,
    ) -> Result<Vec<String>, AppError> {
        let endpoint = format!("{}/rest/v1/rpc/match_provider_services", trim_slash(&self.url));
        let response = self
            .client
            .post(endpoint)
            .header("Authorization", format!("Bearer {}", self.key))
            .header("apikey", &self.key)
            .json(&json!({
                "query_embedding": embedding,
                "similarity_threshold": threshold,
                "match_count": count,
                "city_filter": serde_json::Value::Null,
            }))
            .send()
            .await?;
        if !response.status().is_success() {
            let body = response.text().await.unwrap_or_default();
            return Err(AppError::BadRequest(format!(
                "service search failed: {}",
                body
            )));
        }

        let rows: Vec<serde_json::Value> = response.json().await?;
        let mut results = Vec::new();
        for row in rows {
            for key in [
                "service_name",
                "name",
                "title",
                "category_name",
                "specialty",
                "service_summary",
            ] {
                if let Some(value) = row.get(key).and_then(|value| value.as_str()) {
                    let candidate = value.trim();
                    if !candidate.is_empty() && !results.iter().any(|item| item == candidate) {
                        results.push(candidate.to_string());
                    }
                }
            }
            if results.len() >= count.max(1) as usize {
                break;
            }
        }

        Ok(results)
    }

    pub async fn delete_provider_data(&self, provider_id: &str) -> Result<(), AppError> {
        use urlencoding::encode;
        let id = encode(provider_id);

        let _ = self
            .client
            .delete(format!(
                "{}/rest/v1/provider_whatsapp_identities?provider_id=eq.{}",
                trim_slash(&self.url),
                id
            ))
            .header("Authorization", format!("Bearer {}", self.key))
            .header("apikey", &self.key)
            .send()
            .await;

        let _ = self
            .client
            .delete(format!(
                "{}/rest/v1/consents?user_id=eq.{}",
                trim_slash(&self.url),
                id
            ))
            .header("Authorization", format!("Bearer {}", self.key))
            .header("apikey", &self.key)
            .send()
            .await;

        let _ = self
            .client
            .delete(format!(
                "{}/rest/v1/providers?id=eq.{}",
                trim_slash(&self.url),
                id
            ))
            .header("Authorization", format!("Bearer {}", self.key))
            .header("apikey", &self.key)
            .send()
            .await;

        Ok(())
    }

    pub fn public_url(&self, path: &str) -> String {
        format!(
            "{}/storage/v1/object/public/{}/{}",
            trim_slash(&self.url),
            self.bucket,
            path.trim_start_matches('/')
        )
    }
}

fn trim_slash(value: &str) -> String {
    value.trim_end_matches('/').to_string()
}
