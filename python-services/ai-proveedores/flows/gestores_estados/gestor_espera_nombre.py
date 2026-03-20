"""Manejador del estado awaiting_name."""

from typing import Any, Dict, Optional

from flows.constructores import construir_payload_menu_principal
from flows.validadores import validar_nombre_completo
from services import actualizar_nombre_proveedor
from templates.registro import solicitar_foto_dni_frontal


async def manejar_espera_nombre(
    flujo: Dict[str, Any],
    texto_mensaje: Optional[str],
    supabase: Any = None,
    proveedor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Procesa la entrada del usuario para el campo nombre.

    Args:
        flujo: Diccionario del flujo conversacional.
        texto_mensaje: Mensaje del usuario con el nombre.

    Returns:
        Respuesta con éxito y siguiente pregunta, o error de validación.
    """
    resultado_validacion = validar_nombre_completo(texto_mensaje)
    if not resultado_validacion.get("is_valid"):
        return {
            "success": True,
            "messages": [
                {"response": resultado_validacion.get("message")},
            ],
        }
    nombre = str(resultado_validacion.get("normalized_name") or "").strip()

    if flujo.get("profile_edit_mode") == "personal_name":
        resultado = await actualizar_nombre_proveedor(supabase, proveedor_id, nombre)
        flujo["full_name"] = resultado.get("full_name") or nombre
        flujo.pop("profile_edit_mode", None)
        retorno_estado = str(flujo.pop("profile_return_state", "") or "").strip()
        flujo["state"] = retorno_estado or "awaiting_menu_option"
        if retorno_estado:
            from .gestor_vistas_perfil import render_profile_view

            return {
                "success": True,
                "messages": [
                    {"response": "✅ Tu nombre fue actualizado correctamente."},
                    await render_profile_view(
                        flujo=flujo,
                        estado=retorno_estado,
                        proveedor_id=proveedor_id,
                    ),
                ],
            }
        return {
            "success": True,
            "messages": [
                {"response": "✅ Tu nombre fue actualizado correctamente."},
                construir_payload_menu_principal(
                    esta_registrado=True,
                    menu_limitado=bool(flujo.get("menu_limitado")),
                    approved_basic=bool(flujo.get("approved_basic")),
                ),
            ],
        }

    flujo["name"] = nombre
    flujo["state"] = "awaiting_dni_front_photo"
    return {
        "success": True,
        "messages": [{"response": solicitar_foto_dni_frontal()}],
    }
