from services.proveedores.disponibilidad import ServicioDisponibilidad


def test_mensaje_disponibilidad_incluye_timeout_por_defecto(monkeypatch):
    monkeypatch.delenv("AVAILABILITY_TIMEOUT_SECONDS", raising=False)
    servicio = ServicioDisponibilidad()
    mensaje = servicio._mensaje_disponibilidad_opciones()

    assert "90 segundos" in mensaje


def test_mensaje_disponibilidad_incluye_timeout_configurado(monkeypatch):
    monkeypatch.setenv("AVAILABILITY_TIMEOUT_SECONDS", "75")
    servicio = ServicioDisponibilidad()
    mensaje = servicio._mensaje_disponibilidad_opciones()

    assert "75 segundos" in mensaje
