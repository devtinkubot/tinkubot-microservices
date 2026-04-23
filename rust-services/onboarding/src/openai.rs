use std::time::Duration;

use reqwest::Client;
use serde::{Deserialize, Serialize};

use crate::errors::AppError;

#[derive(Clone)]
pub struct OpenAIClient {
    pub base_url: String,
    pub api_key: String,
    pub model: String,
    pub client: Client,
}

impl OpenAIClient {
    pub fn new(base_url: String, api_key: String, model: String) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(20))
            .build()
            .unwrap_or_else(|_| Client::new());
        Self {
            base_url,
            api_key,
            model,
            client,
        }
    }

    pub async fn get_embedding(&self, text: &str) -> Result<Vec<f32>, AppError> {
        if self.api_key.trim().is_empty() {
            return Err(AppError::BadRequest("openai api key not configured".to_string()));
        }
        let input = text.trim();
        if input.is_empty() {
            return Err(AppError::BadRequest("empty embedding input".to_string()));
        }

        let endpoint = format!("{}/embeddings", self.base_url.trim_end_matches('/'));
        let response = self
            .client
            .post(endpoint)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .header("Content-Type", "application/json")
            .json(&EmbeddingRequest {
                model: self.model.clone(),
                input: input.to_string(),
            })
            .send()
            .await?;
        if !response.status().is_success() {
            let body = response.text().await.unwrap_or_default();
            return Err(AppError::BadRequest(format!("openai embeddings failed: {body}")));
        }

        let payload: EmbeddingResponse = response.json().await?;
        payload
            .data
            .into_iter()
            .next()
            .map(|item| item.embedding)
            .ok_or_else(|| AppError::BadRequest("empty embedding response".to_string()))
    }
}

#[derive(Debug, Serialize)]
struct EmbeddingRequest {
    model: String,
    input: String,
}

#[derive(Debug, Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingData>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
}
