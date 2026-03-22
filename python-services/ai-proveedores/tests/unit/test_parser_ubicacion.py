from services.registro.parser_ubicacion import (
    VALIDATION_ERROR_UNKNOWN,
    VALIDATION_OK,
    validar_y_normalizar_ubicacion,
)


def test_autocorrige_entrada_compuesta_y_conserva_ciudad():
    ubicacion, estado = validar_y_normalizar_ubicacion("Cuenca, Azuay, Ecuador")
    assert estado == VALIDATION_OK
    assert ubicacion == "Cuenca"


def test_extrae_ciudad_desde_direccion_completa_con_numeros():
    ubicacion, estado = validar_y_normalizar_ubicacion(
        "Polideportivo, Ave Los Andes 246, Cuenca, 010209, A, EC"
    )
    assert estado == VALIDATION_OK
    assert ubicacion == "Cuenca"


def test_acepta_canton_nabon():
    ubicacion, estado = validar_y_normalizar_ubicacion("Nabon")
    assert estado == VALIDATION_OK
    assert ubicacion == "Nabón"


def test_rechaza_provincia_como_ubicacion():
    ubicacion, estado = validar_y_normalizar_ubicacion("Azuay")
    assert ubicacion is None
    assert estado == VALIDATION_ERROR_UNKNOWN
