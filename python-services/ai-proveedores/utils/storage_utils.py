"""
Utilidades de almacenamiento para normalización de datos de Supabase Storage.
"""
import json
import re
from typing import Any, Dict, List, Optional, Set


def _coerce_storage_string(value: Any) -> Optional[str]:
    """
    Normaliza diferentes formatos devueltos por Supabase Storage (string, dict o StorageResponse)
    y retorna una URL o path utilizable.
    """

    def _from_mapping(mapping: Dict[str, Any]) -> Optional[str]:
        if not isinstance(mapping, dict):
            return None

        for key in ("publicUrl", "public_url", "signedUrl", "signed_url", "url", "href"):
            candidate = mapping.get(key)
            if isinstance(candidate, str):
                candidate = candidate.strip()
                if candidate:
                    return candidate

        path_candidate = mapping.get("path") or mapping.get("filePath")
        if isinstance(path_candidate, str):
            path_candidate = path_candidate.strip()
            if path_candidate:
                return path_candidate

        return None

    if not value:
        return None

    if isinstance(value, str):
        value = value.strip()
        return value or None

    if isinstance(value, dict):
        direct = _from_mapping(value)
        if direct:
            return direct
        nested = value.get("data")
        if isinstance(nested, dict):
            nested_value = _from_mapping(nested)
            if nested_value:
                return nested_value
        return None

    data_attr = getattr(value, "data", None)
    if isinstance(data_attr, dict):
        nested_value = _from_mapping(data_attr)
        if nested_value:
            return nested_value

    for attr_name in ("public_url", "publicUrl", "signed_url", "signedUrl", "url"):
        attr_value = getattr(value, attr_name, None)
        if isinstance(attr_value, str):
            attr_value = attr_value.strip()
            if attr_value:
                return attr_value

    path_attr = getattr(value, "path", None)
    if isinstance(path_attr, str):
        path_attr = path_attr.strip()
        if path_attr:
            return path_attr

    json_candidate = None
    if hasattr(value, "json"):
        try:
            json_candidate = value.json()
        except Exception:
            json_candidate = None
        if isinstance(json_candidate, dict):
            nested_value = _from_mapping(json_candidate)
            if nested_value:
                return nested_value

    text_attr = getattr(value, "text", None)
    if isinstance(text_attr, str) and text_attr.strip():
        parsed = _safe_json_loads(text_attr.strip())
        if isinstance(parsed, dict):
            nested_value = _from_mapping(parsed)
            if nested_value:
                return nested_value

    return None


def _safe_json_loads(payload: str) -> Optional[Any]:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]|\{.*\}", payload, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None


def _normalize_terms(values: Optional[List[Any]]) -> List[str]:
    normalized: List[str] = []
    if not values:
        return normalized
    seen: Set[str] = set()
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def extract_first_image_base64(payload: Dict[str, Any]) -> Optional[str]:
    candidates = [
        payload.get("image_base64"),
        payload.get("media_base64"),
        payload.get("file_base64"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    attachments = payload.get("attachments") or payload.get("media") or []
    if isinstance(attachments, dict):
        attachments = [attachments]
    for item in attachments:
        if not isinstance(item, dict):
            continue
        if item.get("type") and item["type"].lower() not in {
            "image",
            "photo",
            "picture",
        }:
            continue
        data = item.get("base64") or item.get("data") or item.get("content")
        if isinstance(data, str) and data.strip():
            return data.strip()

    content = payload.get("content") or payload.get("message")
    if isinstance(content, str) and content.startswith("data:image/"):
        return content

    return None
