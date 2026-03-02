from flows.mensajes import solicitar_ciudad, solicitar_ciudad_con_servicio


def test_solicitar_ciudad_incluye_location_request_ui():
    respuesta = solicitar_ciudad()
    assert respuesta["response"]
    assert respuesta["ui"]["type"] == "location_request"
    assert respuesta["ui"]["id"] == "location_request_city_initial"


def test_solicitar_ciudad_con_servicio_incluye_location_request_ui():
    respuesta = solicitar_ciudad_con_servicio("plomero")
    assert "plomero" in respuesta["response"]
    assert respuesta["ui"]["type"] == "location_request"
    assert respuesta["ui"]["id"] == "location_request_city_with_service"
