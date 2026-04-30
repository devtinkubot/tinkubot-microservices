use std::collections::BTreeMap;

use chrono::Utc;
use deadpool_redis::Pool;
use sha2::{Digest, Sha256};

use crate::errors::AppError;

pub async fn publish_onboarding_event(
    pool: &Pool,
    stream_key: &str,
    maxlen: u64,
    event_type: &str,
    provider_id: &str,
    phone: &str,
    step: &str,
    checkpoint: &str,
    source_message_id: &str,
    payload: &serde_json::Value,
) -> Result<String, AppError> {
    let occurred_at = Utc::now().to_rfc3339();
    let payload_json = serde_json::to_string(payload)?;
    let idempotency_key = build_idempotency_key(event_type, provider_id, phone, source_message_id, &payload_json);

    let mut fields = BTreeMap::new();
    fields.insert("event_type", event_type.to_string());
    fields.insert("provider_id", provider_id.to_string());
    fields.insert("phone", phone.to_string());
    fields.insert("step", step.to_string());
    fields.insert("checkpoint", checkpoint.to_string());
    fields.insert("source_message_id", source_message_id.to_string());
    fields.insert("idempotency_key", idempotency_key);
    fields.insert("occurred_at", occurred_at);
    fields.insert("payload", payload_json);

    let mut conn = pool.get().await?;
    let mut cmd = deadpool_redis::redis::cmd("XADD");
    cmd.arg(stream_key).arg("MAXLEN").arg("~").arg(maxlen).arg("*");
    for (field, value) in fields {
        cmd.arg(field).arg(value);
    }
    let entry_id: String = cmd.query_async(&mut conn).await?;
    Ok(entry_id)
}

fn build_idempotency_key(
    event_type: &str,
    provider_id: &str,
    phone: &str,
    source_message_id: &str,
    payload_json: &str,
) -> String {
    let mut hasher = Sha256::new();
    hasher.update(event_type.as_bytes());
    hasher.update(provider_id.as_bytes());
    hasher.update(phone.as_bytes());
    hasher.update(source_message_id.as_bytes());
    hasher.update(payload_json.as_bytes());
    hex::encode(hasher.finalize())
}
