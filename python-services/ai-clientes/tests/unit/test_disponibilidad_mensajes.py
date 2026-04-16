from services.proveedores.disponibilidad import ServicioDisponibilidad


class _RepositorioMetricasRotacionFalso:
    async def obtener_metricas_proveedores(self, provider_ids, dias=30):
        _ = provider_ids, dias
        return {}


def _crear_servicio():
    return ServicioDisponibilidad(
        repositorio_metricas=_RepositorioMetricasRotacionFalso()
    )


def test_mensaje_disponibilidad_incluye_timeout_por_defecto(monkeypatch):
    monkeypatch.delenv("AVAILABILITY_TIMEOUT_SECONDS", raising=False)
    servicio = _crear_servicio()
    mensaje = servicio._mensaje_disponibilidad_fallback()

    assert "Tienes 3 min para responder." in mensaje


def test_mensaje_disponibilidad_incluye_timeout_configurado(monkeypatch):
    monkeypatch.setenv("AVAILABILITY_TIMEOUT_SECONDS", "180")
    servicio = _crear_servicio()
    mensaje = servicio._mensaje_disponibilidad_fallback()

    assert "Tienes 3 min para responder." in mensaje


def test_mensaje_disponibilidad_contexto_usa_primer_nombre_y_copy_nuevo():
    servicio = _crear_servicio()

    mensaje = servicio._mensaje_disponibilidad_contexto(
        nombre="Diego Unkuch Gonzalez",
        servicio="desarrollo y mantenimiento de aplicaciones móviles",
        ciudad="Cuenca",
        descripcion_problema=(
            "Qué alguien desarrolle la app movil y arregle los errores que tiene"
        ),
    )

    assert "*Oportunidad en Cuenca*" in mensaje
    assert (
        "*Se requiere:* desarrollo y mantenimiento de aplicaciones móviles" in mensaje
    )
    assert (
        "*Necesidad del cliente:* desarrolle la app movil y arregle los errores "
        "que tiene" in mensaje
    )
    assert "Hola *Diego*" not in mensaje
    assert "*Para resolver:*" not in mensaje


def test_ui_disponibilidad_expone_template_esperado():
    servicio = _crear_servicio()

    ui = servicio._ui_disponibilidad(
        servicio="desarrollo y mantenimiento de aplicaciones móviles",
        ciudad="Cuenca",
        descripcion_problema=(
            "Qué alguien desarrolle la app movil y arregle los errores que tiene"
        ),
    )

    assert ui["type"] == "template"
    assert ui["template_name"] == "provider_availability_request_v1"
    assert ui["template_language"] == "es"
    assert ui["template_components"] == [
        {
            "type": "header",
            "parameters": [{"type": "text", "text": "Cuenca"}],
        },
        {
            "type": "body",
            "parameters": [
                {
                    "type": "text",
                    "text": "desarrollo y mantenimiento de aplicaciones móviles",
                },
                {
                    "type": "text",
                    "text": "desarrolle la app movil y arregle los errores que tiene",
                },
            ],
        },
        {
            "type": "button",
            "sub_type": "quick_reply",
            "index": "0",
            "parameters": [{"type": "payload", "payload": "availability_accept"}],
        },
        {
            "type": "button",
            "sub_type": "quick_reply",
            "index": "1",
            "parameters": [{"type": "payload", "payload": "availability_reject"}],
        },
    ]
