from services.registro.validacion_registro import validar_y_construir_proveedor


def test_validacion_registro_rechaza_provincia_en_city():
    flujo = {
        "name": "Proveedor Demo",
        "city": "Azuay",
        "has_consent": True,
    }

    ok, error, proveedor = validar_y_construir_proveedor(
        flujo=flujo,
        telefono="593999999999@s.whatsapp.net",
    )

    assert ok is False
    assert proveedor is None
    assert error is not None
    assert "ciudad" in error


def test_validacion_registro_autocorrige_ciudad_compuesta():
    flujo = {
        "name": "Proveedor Demo",
        "city": "Cuenca, Azuay, Ecuador",
        "has_consent": True,
    }

    ok, error, proveedor = validar_y_construir_proveedor(
        flujo=flujo,
        telefono="593999999999@s.whatsapp.net",
    )

    assert ok is True
    assert error is None
    assert proveedor is not None
    assert proveedor.city == "Cuenca"
    assert proveedor.services_list == []
