import asyncio
import sys
import types
from pathlib import Path

imghdr_stub = types.ModuleType("imghdr")
imghdr_stub.what = lambda *args, **kwargs: None  # type: ignore[attr-defined]
sys.modules.setdefault("imghdr", imghdr_stub)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import flows.router as modulo_router  # noqa: E402


def _logger():
    return types.SimpleNamespace(info=lambda *args, **kwargs: None)


def test_flujo_sin_estado_vuelve_menu_principal():
    resultado = asyncio.run(
        modulo_router._manejar_flujo_sin_estado(
            flujo={},
            telefono="593999111299@s.whatsapp.net",
            perfil_proveedor=None,
            logger=_logger(),
        )
    )

    assert resultado["persist_flow"] is True
    assert resultado["new_flow"]["state"] == "awaiting_menu_option"
    assert resultado["response"]["messages"][0]["ui"]["id"] == "provider_onboarding_continue_v1"


def test_manejar_mensaje_sin_flujo_vuelve_menu_principal():
    flujo = {}

    resultado = asyncio.run(
        modulo_router.manejar_mensaje(
            flujo=flujo,
            telefono="593999111299@s.whatsapp.net",
            texto_mensaje="hola",
            carga={},
            opcion_menu=None,
            perfil_proveedor=None,
            supabase=None,
            servicio_embeddings=None,
            cliente_openai=None,
            subir_medios_identidad=lambda *args, **kwargs: None,
            logger=_logger(),
        )
    )

    assert resultado["persist_flow"] is True
    assert resultado["response"]["messages"][0]["ui"]["id"] == "provider_onboarding_continue_v1"
