from services.proveedores.disponibilidad import ServicioDisponibilidad


def test_mensaje_disponibilidad_incluye_timeout_por_defecto(monkeypatch):
    monkeypatch.delenv("AVAILABILITY_TIMEOUT_SECONDS", raising=False)
    servicio = ServicioDisponibilidad()
    mensaje = servicio._mensaje_disponibilidad_fallback()

    assert "Tienes 2 min para responder." in mensaje


def test_mensaje_disponibilidad_incluye_timeout_configurado(monkeypatch):
    monkeypatch.setenv("AVAILABILITY_TIMEOUT_SECONDS", "120")
    servicio = ServicioDisponibilidad()
    mensaje = servicio._mensaje_disponibilidad_fallback()

    assert "Tienes 2 min para responder." in mensaje


def test_mensaje_disponibilidad_contexto_usa_primer_nombre_y_copy_nuevo():
    servicio = ServicioDisponibilidad()

    mensaje = servicio._mensaje_disponibilidad_contexto(
        nombre="Diego Unkuch Gonzalez",
        servicio="desarrollo y mantenimiento de aplicaciones móviles",
        ciudad="Cuenca",
        descripcion_problema="Qué alguien desarrolle la app movil y arregle los errores que tiene",
    )

    assert "*Oportunidad en Cuenca*" in mensaje
    assert "*Se requiere:* desarrollo de apps moviles a medida" in mensaje
    assert (
        "*Necesidad del cliente:* necesita arreglar una app movil del trabajo "
        "que no esta funcionando bien"
    ) in mensaje
    assert "Hola *Diego*" not in mensaje
    assert "*Para resolver:*" not in mensaje


def test_ui_disponibilidad_expone_botones_esperados():
    servicio = ServicioDisponibilidad()

    ui = servicio._ui_disponibilidad()

    assert ui["type"] == "buttons"
    assert ui["id"] == "provider_availability_v1"
    assert ui["footer_text"] == "Tienes 2 min para responder."
    assert ui["options"] == [
        {"id": "availability_accept", "title": "Disponible"},
        {"id": "availability_reject", "title": "No disponible"},
    ]
