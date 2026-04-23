use deadpool_redis::{redis::AsyncCommands, Pool};

use crate::{errors::AppError, models::FlowState};

#[derive(Clone)]
pub struct RedisStore {
    pub pool: Pool,
}

impl RedisStore {
    pub fn new(pool: Pool) -> Self {
        Self { pool }
    }

    pub fn key_for(phone: &str) -> String {
        format!("prov_flow:{phone}")
    }

    pub async fn get_flow(&self, phone: &str) -> Result<Option<FlowState>, AppError> {
        let mut conn = self.pool.get().await?;
        let key = Self::key_for(phone);
        let value: Option<String> = conn.get(key).await?;
        match value {
            Some(json) => Ok(Some(serde_json::from_str(&json)?)),
            None => Ok(None),
        }
    }

    pub async fn set_flow(&self, flow: &FlowState) -> Result<(), AppError> {
        let mut conn = self.pool.get().await?;
        let key = Self::key_for(&flow.phone);
        let json = serde_json::to_string(flow)?;
        conn.set::<_, _, ()>(key, json).await?;
        Ok(())
    }

    pub async fn delete_flow(&self, phone: &str) -> Result<(), AppError> {
        let mut conn = self.pool.get().await?;
        let key = Self::key_for(phone);
        conn.del::<_, ()>(key).await?;
        Ok(())
    }
}
