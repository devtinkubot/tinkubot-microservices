from flows.gestores_estados.gestor_espera_ciudad import manejar_espera_ciudad


def test_manejar_espera_ciudad_autocorrige_y_avanza_estado():
    flujo = {"state": "awaiting_city"}
    respuesta = manejar_espera_ciudad(flujo, "Cuenca, Azuay, Ecuador")

    assert respuesta["success"] is True
    assert flujo["city"] == "cuenca"
    assert flujo["state"] == "awaiting_name"


def test_manejar_espera_ciudad_rechaza_provincia():
    flujo = {"state": "awaiting_city"}
    respuesta = manejar_espera_ciudad(flujo, "Azuay")

    assert respuesta["success"] is True
    assert flujo["state"] == "awaiting_city"
    assert "No reconocí esa ubicación" in respuesta["messages"][0]["response"]
