"""Tests para normalización de respuestas hacia wa-gateway."""

from services.respuesta_whatsapp import normalizar_respuesta_whatsapp


def test_normalizar_respuesta_envuelve_response_simple():
    resultado = normalizar_respuesta_whatsapp({"response": "hola"})

    assert resultado == {
        "success": True,
        "messages": [{"response": "hola"}],
    }


def test_normalizar_respuesta_elimina_duplicados_adyacentes():
    resultado = normalizar_respuesta_whatsapp(
        {
            "messages": [
                {"response": "¿Es este el servicio que buscas: servicio de carpintería?"},
                {"response": "¿Es este el servicio que buscas: servicio de carpintería?"},
                {"response": "⏳ Busco expertos. Te aviso en breve."},
            ]
        }
    )

    assert resultado["success"] is True
    assert resultado["messages"] == [
        {"response": "¿Es este el servicio que buscas: servicio de carpintería?"},
        {"response": "⏳ Busco expertos. Te aviso en breve."},
    ]
