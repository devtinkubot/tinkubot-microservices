use serde::{Deserialize, Serialize};
use validator::Validate;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LocationPayload {
    pub latitude: f64,
    pub longitude: f64,
    pub name: Option<String>,
    pub address: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Validate)]
pub struct WebhookPayload {
    #[validate(length(min = 1))]
    pub phone: String,
    pub from_number: Option<String>,
    pub user_id: Option<String>,
    pub display_name: Option<String>,
    pub formatted_name: Option<String>,
    pub first_name: Option<String>,
    pub last_name: Option<String>,
    pub username: Option<String>,
    pub country_code: Option<String>,
    pub context_from: Option<String>,
    pub context_id: Option<String>,
    pub content: Option<String>,
    #[validate(length(min = 1))]
    pub message: String,
    pub message_type: Option<String>,
    pub selected_option: Option<String>,
    pub flow_payload: Option<serde_json::Value>,
    pub location: Option<LocationPayload>,
    #[validate(length(min = 1))]
    pub timestamp: String,
    pub id: Option<String>,
    #[validate(length(min = 1))]
    pub account_id: String,
    pub media_base64: Option<String>,
    pub media_mimetype: Option<String>,
    pub media_filename: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct FlowState {
    pub phone: String,
    pub provider_id: String,
    pub state: String,
    pub checkpoint: Option<String>,
    pub step: Option<String>,
    pub last_message_id: Option<String>,
    pub updated_at: Option<String>,
    #[serde(default)]
    pub has_consent: bool,
    #[serde(default)]
    pub real_phone: Option<String>,
    #[serde(default)]
    pub city: Option<String>,
    #[serde(default)]
    pub experience_range: Option<String>,
    #[serde(default)]
    pub services: Vec<String>,
    #[serde(default)]
    pub specialty: Option<String>,
    #[serde(default)]
    pub dni_front_url: Option<String>,
    #[serde(default)]
    pub face_photo_url: Option<String>,
    #[serde(default)]
    pub facebook_username: Option<String>,
    #[serde(default)]
    pub instagram_username: Option<String>,
    #[serde(default)]
    pub onboarding_complete: bool,
}

impl FlowState {
    pub fn new(phone: String, provider_id: String, state: String) -> Self {
        Self {
            phone,
            provider_id,
            state,
            checkpoint: None,
            step: None,
            last_message_id: None,
            updated_at: None,
            has_consent: false,
            real_phone: None,
            city: None,
            experience_range: None,
            services: Vec::new(),
            specialty: None,
            dni_front_url: None,
            face_photo_url: None,
            facebook_username: None,
            instagram_username: None,
            onboarding_complete: false,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ResponseMessage {
    pub response: String,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OnboardingResponse {
    pub success: bool,
    pub messages: Vec<ResponseMessage>,
}

impl OnboardingResponse {
    pub fn single(response: impl Into<String>) -> Self {
        Self { success: true, messages: vec![ResponseMessage { response: response.into() }] }
    }
}
