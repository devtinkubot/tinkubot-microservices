from unittest.mock import AsyncMock, MagicMock

import pytest

from flows.busqueda_proveedores.ejecutor_busqueda_en_segundo_plano import (
    ejecutar_busqueda_y_notificar_en_segundo_plano,
)


class _ServicioDisponibilidadStub:
    async def verificar_disponibilidad(self, **kwargs):
        return {
            "aceptados": kwargs.get("candidatos") or [],
            "request_id": "req-123",
        }

    async def marcar_solicitud_como_presentada(self, **kwargs):
        return None

    async def cerrar_solicitud(self, **kwargs):
        return None


@pytest.mark.asyncio
async def test_prefetch_cache_vacio_no_bloquea_busqueda_viva(monkeypatch):
    servicio_disponibilidad_stub = _ServicioDisponibilidadStub()
    monkeypatch.setattr(
        "principal.servicio_disponibilidad",
        servicio_disponibilidad_stub,
        raising=False,
    )
    monkeypatch.setattr(
        "infrastructure.prefetch.publicador_prefetch.obtener_prefetch_cache",
        AsyncMock(return_value={"providers": []}),
    )

    enviar_mensaje_callback = AsyncMock(return_value=True)
    guardar_flujo_callback = AsyncMock()
    buscar_proveedores_fn = AsyncMock(
        return_value={
            "providers": [
                {
                    "id": "prov-1",
                    "name": "Diego Unkuch Gonzalez",
                    "phone_number": "593999111222",
                    "real_phone": "593999111222",
                }
            ]
        }
    )

    flujo = {
        "service": "desarrollo de aplicaciones móviles",
        "service_full": "desarrollo de aplicaciones móviles",
        "service_domain": "tecnología",
        "service_domain_code": "tecnologia",
        "service_category": "desarrollo de aplicaciones móviles",
        "service_category_name": "desarrollo de aplicaciones moviles",
        "city": "Cuenca",
        "descripcion_problema": "Necesito un desarrollador de apps moviles",
    }

    supabase_client = MagicMock()
    supabase_client.table.return_value.insert.return_value.execute.return_value = None

    await ejecutar_busqueda_y_notificar_en_segundo_plano(
        telefono="593959091325@s.whatsapp.net",
        flujo=flujo,
        enviar_mensaje_callback=enviar_mensaje_callback,
        guardar_flujo_callback=guardar_flujo_callback,
        buscar_proveedores_fn=buscar_proveedores_fn,
        supabase_client=supabase_client,
    )

    buscar_proveedores_fn.assert_awaited_once()
    assert flujo["state"] == "presenting_results"
    assert flujo["providers"]
    guardar_flujo_callback.assert_awaited()
