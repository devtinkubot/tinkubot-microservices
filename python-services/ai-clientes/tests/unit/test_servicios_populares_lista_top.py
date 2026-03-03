"""Tests de formato Top N y mapeo de selección en lista de servicios."""

from templates.mensajes.validacion import (
    POPULAR_SERVICE_PREFIX,
    construir_opciones_servicios_populares,
    extraer_servicio_desde_opcion_lista,
)


def test_construir_opciones_top_n_con_description():
    opciones = construir_opciones_servicios_populares(
        ["Plomero", "Electricista", "Técnico de lavadoras"]
    )

    assert opciones[0]["title"] == "Top 1"
    assert opciones[0]["description"] == "Plomero"
    assert opciones[0]["id"].startswith(POPULAR_SERVICE_PREFIX)
    assert opciones[1]["title"] == "Top 2"
    assert opciones[1]["description"] == "Electricista"


def test_extraer_servicio_desde_selected_option_por_slug():
    servicio = extraer_servicio_desde_opcion_lista(
        f"{POPULAR_SERVICE_PREFIX}tecnico_de_lavadoras"
    )

    assert servicio == "Técnico de lavadoras"


def test_extraer_servicio_desde_selected_option_en_fallback_usa_description():
    servicios = ["Plomero", "Electricista"]
    opciones = construir_opciones_servicios_populares(servicios)
    selected = opciones[0]["id"]

    servicio = extraer_servicio_desde_opcion_lista(selected, servicios=servicios)

    assert servicio == "Plomero"
