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

    pub async fn upload_to_storage(
        &self,
        path: &str,
        data: &[u8],
        content_type: &str,
    ) -> Result<String, AppError> {
        let clean_path = path.trim_start_matches('/');
        let endpoint = format!(
            "{}/storage/v1/object/{}/{}",
            trim_slash(&self.url),
            self.bucket,
            clean_path
        );
        let response = self
            .client
            .put(endpoint)
            .header("Authorization", format!("Bearer {}", self.key))
            .header("apikey", &self.key)
            .header("x-upsert", "true")
            .header("content-type", content_type)
            .body(data.to_vec())
            .send()
            .await?;
        if !response.status().is_success() {
            let body = response.text().await.unwrap_or_default();
            return Err(AppError::BadRequest(format!(
                "storage upload failed: {}",
                body
            )));
        }
        Ok(self.public_url(clean_path))
    }

    pub async fn search_similar_services(
        &self,
        embedding: &[f32],
        threshold: f32,
        count: i32,
    ) -> Result<Vec<String>, AppError> {
        let endpoint = format!("{}/rest/v1/rpc/match_services", trim_slash(&self.url));
        let response = self
            .client
            .post(endpoint)
            .header("Authorization", format!("Bearer {}", self.key))
            .header("apikey", &self.key)
            .json(&json!({
                "query_embedding": embedding,
                "match_threshold": threshold,
                "match_count": count,
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
