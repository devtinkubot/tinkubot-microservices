#![allow(unused_imports)]

mod experience;
mod image;
mod phone;
mod security;
mod social_media;
mod text;

pub use experience::normalize_experience;
pub use image::{validate_base64_image, ValidatedImage};
pub use phone::{extract_real_phone_from_jid, is_lid_or_bsuid, normalize_ecuador_phone};
pub use security::validate_url;
pub use social_media::{parse_social_urls, SocialMediaLinks};
pub use text::{is_affirmative, is_negative, normalize_text};
