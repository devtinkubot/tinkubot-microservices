from templates.busqueda.confirmacion import (
    mensaje_buscando_expertos,
    mensaje_confirmando_disponibilidad,
    mensaje_expertos_encontrados,
)


def test_mensaje_buscando_expertos_copy():
    assert mensaje_buscando_expertos == "⏳ *Busco expertos.* Te aviso en breve."


def test_mensaje_confirmando_disponibilidad_copy():
    assert (
        mensaje_confirmando_disponibilidad
        == "⏳ *Confirmo disponibilidad.* Te aviso en 3 min."
    )


def test_mensaje_expertos_encontrados_singular():
    assert mensaje_expertos_encontrados(1, "Cuenca") == "✅ Encontre *1* experto en *Cuenca*."


def test_mensaje_expertos_encontrados_plural():
    assert mensaje_expertos_encontrados(3, "Cuenca") == "✅ Encontre *3* expertos en *Cuenca*."
