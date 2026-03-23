import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None
sys.modules.setdefault("imghdr", imghdr_stub)


@pytest.fixture(autouse=True)
def _provider_registration_header_url_env(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_ONBOARDING_BTN_REGISTRARSE_HEADER_URL",
        "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
        "tinkubot-assets/images/tinkubot_provider_start_register.png?token="
        "eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
        "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1h"
        "c3NldHMvaW1hZ2VzL3Rpbmt1Ym90X3Byb3ZpZGVyX3N0YXJ0X3JlZ2lzdGVyLnBuZyIsIml"
        "hdCI6MTc3NDE1MTgzOCwiZXhwIjo0ODk2MjE1ODM4fQ.xWUhhlYF66t-hGFYjqvIewGB2C"
        "yjXpeCgdqjAMAduBI"
    )


@pytest.fixture(autouse=True)
def _provider_onboarding_document_images_env(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_ONBOARDING_DNI_FRONT_GUIDE_URL",
        "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
        "tinkubot-assets/images/tinkubot_dni_photo.png?token="
        "eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
        "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1h"
        "c3NldHMvaW1hZ2VzL3Rpbmt1Ym90X2RuaV9waG90by5wbmciLCJpYXQiOjE3NzQxNTMw"
        "NzAsImV4cCI6MTc4MjcwNjY3MH0.wrabaTxYBJaxqS_NtCFePQhLqj9Xhraz6LIk0ymvErE"
    )
    monkeypatch.setenv(
        "WA_PROVIDER_ONBOARDING_PROFILE_PHOTO_GUIDE_URL",
        "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
        "tinkubot-assets/images/tinkubot_profile_photo.png?token="
        "eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
        "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1h"
        "c3NldHMvaW1hZ2VzL3Rpbmt1Ym90X3Byb2ZpbGVfcGhvdG8ucG5nIiwiaWF0IjoxNzc0MT"
        "UzMTI2LCJleHAiOjE3ODI3MDY3MjZ9.2WNNHtLxPx6P3BzoLWxONG5kiUcWNFl10AF-lYI"
        "HKRo"
    )


@pytest.fixture(autouse=True)
def _provider_services_image_url_env(monkeypatch):
    monkeypatch.setenv(
        "WA_PROVIDER_SERVICES_IMAGE_URL",
        "https://euescxureboitxqjduym.supabase.co/storage/v1/object/sign/"
        "tinkubot-assets/images/tinkubot_add_services.png?token="
        "eyJraWQiOiJzdG9yYWdlLXVybC1zaWduaW5nLWtleV8wMTQwMDNkYS1hOWY0LTQ1YmYt"
        "OTE1Zi1hZmYzZTExNDhhODciLCJhbGciOiJIUzI1NiJ9.eyJ1cmwiOiJ0aW5rdWJvdC1h"
        "c3NldHMvaW1hZ2VzL3Rpbmt1Ym90X2FkZF9zZXJ2aWNlcy5wbmciLCJpYXQiOjE3NzQyNj"
        "k3OTksImV4cCI6NDg5NjMzMzc5OX0.ORwyhoGWMehxcpYaxgIasohvCZ5AD4di5Ie9kQGF"
        "zI"
    )
