from services.proveedores.conexion import mensaje_conexion_formal
from templates.proveedores.conexion import mensaje_notificacion_conexion


def test_mensaje_notificacion_conexion_retorna_contact_card():
    payload = mensaje_notificacion_conexion(
        {"first_name": "Diego", "last_name": "Unkuch Gonzalez"},
        telefono_contacto="593959091325",
    )

    assert payload["response"] == ""
    assert len(payload["contacts"]) == 1
    assert payload["contacts"][0]["name"]["formatted_name"] == "Diego Unkuch Gonzalez"
    assert payload["contacts"][0]["name"]["first_name"] == "Diego"
    assert payload["contacts"][0]["phones"][0]["phone"] == "+593959091325"
    assert payload["contacts"][0]["phones"][0]["wa_id"] == "593959091325"


def test_mensaje_notificacion_conexion_sin_telefono_hace_fallback_textual():
    payload = mensaje_notificacion_conexion(
        {"first_name": "Diego", "last_name": "Unkuch Gonzalez"},
        telefono_contacto=None,
    )

    assert payload == {
        "response": (
            "Te comparto el contacto de *Diego Unkuch Gonzalez* para que coordines "
            "tu servicio."
        )
    }


def test_mensaje_conexion_formal_genera_contacto_desde_jid():
    payload = mensaje_conexion_formal(
        {
            "name": "Diego Unkuch Gonzalez",
            "phone_number": "593959091325@s.whatsapp.net",
        },
        supabase=None,
        bucket="",
        supabase_base_url="",
    )

    assert payload["contacts"][0]["phones"][0]["wa_id"] == "593959091325"
