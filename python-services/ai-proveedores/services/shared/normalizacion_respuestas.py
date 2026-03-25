"""Normalización compartida de respuestas de usuario."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


PALABRAS_DISPARO_REGISTRO = {
    "registro",
    "registrarme",
    "registrarse",
    "registrar",
    "soy proveedor",
    "quiero ofrecer",
    "ofrecer servicios",
    "unirme",
    "alta proveedor",
    "crear perfil",
}

PALABRAS_REINICIO = {
    "reset",
    "reiniciar",
    "reinicio",
    "empezar",
    "inicio",
    "comenzar",
    "start",
    "nuevo",
}

VALOR_OPCION_AFIRMATIVA = "1"
VALOR_OPCION_NEGATIVA = "2"

RESPUESTAS_SI = {
    VALOR_OPCION_AFIRMATIVA,
    "si",
}

RESPUESTAS_NO = {
    VALOR_OPCION_NEGATIVA,
    "no",
}

RESPUESTAS_CONSENTIMIENTO_AFIRMATIVAS = {
    "s",
    "acepto",
    "autorizo",
    "confirmo",
    "claro",
    "de acuerdo",
} | RESPUESTAS_SI

RESPUESTAS_CONSENTIMIENTO_NEGATIVAS = {
    "n",
    "rechazo",
    "rechazar",
    "declino",
    "no autorizo",
} | RESPUESTAS_NO

RESPUESTAS_CONFIRMACION_REGISTRO_AFIRMATIVAS = {
    "ok",
    "listo",
    "confirmar",
} | RESPUESTAS_SI

RESPUESTAS_CONFIRMACION_REGISTRO_NEGATIVAS = {
    "cancelar",
    "rechazo",
} | RESPUESTAS_NO

SELECCION_CONSENTIMIENTO_AFIRMATIVA = {
    "continue_provider_onboarding",
    "continuar",
    "continue",
    "1",
}

SELECCION_CONSENTIMIENTO_NEGATIVA = {
    "2",
    "rechazar",
    "decline",
    "cancelar",
}

SELECCION_CONFIRMACION_REGISTRO_AFIRMATIVA = {
    "confirm_accept",
    "accept",
    "1",
}

SELECCION_CONFIRMACION_REGISTRO_NEGATIVA = {
    "confirm_reject",
    "reject",
    "2",
}

SELECCION_CONFIRMACION_SERVICIOS_AFIRMATIVA = {
    "profile_service_confirm",
    "accept",
    "1",
}

SELECCION_CONFIRMACION_SERVICIOS_NEGATIVA = {
    "profile_service_correct",
    "reject",
    "2",
}

SELECCION_AGREGAR_SERVICIO_AFIRMATIVA = {"1"}
SELECCION_AGREGAR_SERVICIO_NEGATIVA = {"2"}

RESPUESTAS_CONFIRMACION_SERVICIOS_AFIRMATIVAS = {
    "aceptar",
    "acepto",
    "confirmar",
} | RESPUESTAS_SI

RESPUESTAS_CONFIRMACION_SERVICIOS_NEGATIVAS = {
    "corregir",
    "editar",
    "cambiar",
    "no acepto",
} | RESPUESTAS_NO

RESPUESTAS_AGREGAR_SERVICIO_AFIRMATIVAS = {
    "agregar",
    "otro",
    "continuar",
} | RESPUESTAS_SI

RESPUESTAS_AGREGAR_SERVICIO_NEGATIVAS = {
    "terminar",
    "listo",
} | RESPUESTAS_NO

RESPUESTAS_ELIMINACION_AFIRMATIVAS = {
    "confirmar",
    "eliminar",
} | RESPUESTAS_SI

RESPUESTAS_ELIMINACION_NEGATIVAS = {
    "cancelar",
} | RESPUESTAS_NO

RESPUESTAS_DISPONIBILIDAD_AFIRMATIVAS = {
    "s",
    "ok",
    "dale",
    "disponible",
    "acepto",
} | RESPUESTAS_SI

RESPUESTAS_DISPONIBILIDAD_NEGATIVAS = {
    "n",
    "ocupado",
    "no disponible",
} | RESPUESTAS_NO

SALIDA_MENU_PALABRAS = {
    "menu",
    "volver",
    "salir",
    "regresar",
}

SKIP_VALUES_UNIVERSALES = {
    "omitir",
    "na",
    "n/a",
    "ninguno",
    "null",
    "none",
}

OPCIONES_MENU_SERVICIOS_AGREGAR = {"1", "agregar"}
OPCIONES_MENU_SERVICIOS_ELIMINAR = {"2", "eliminar"}
OPCIONES_MENU_SERVICIOS_VOLVER = {"3", "volver", "salir"}

OPCIONES_EDICION_SERVICIOS_REEMPLAZAR = {"1", "reemplazar"}
OPCIONES_EDICION_SERVICIOS_ELIMINAR = {"2", "eliminar"}
OPCIONES_EDICION_SERVICIOS_AGREGAR = {"3", "agregar"}
OPCIONES_EDICION_SERVICIOS_RESUMEN = {"4", "volver", "resumen"}


def normalizar_texto_interaccion(text: Optional[str]) -> str:
    value = (text or "").strip().lower()
    if not value:
        return ""
    normalized_value = unicodedata.normalize("NFKD", value)
    normalized_value = normalized_value.encode("ascii", "ignore").decode()
    normalized_value = re.sub(r"[\s\.,;:!¡¿\?]+", " ", normalized_value)
    normalized_value = " ".join(normalized_value.split())
    return normalized_value


def es_comando_reinicio(text: Optional[str]) -> bool:
    """Detecta si el texto pide reiniciar el flujo."""
    normalized_value = normalizar_texto_interaccion(text)
    return bool(normalized_value and normalized_value in PALABRAS_REINICIO)


def es_disparador_registro(text: Optional[str]) -> bool:
    """Detecta si el texto indica una intención de registro."""
    normalized_value = normalizar_texto_interaccion(text)
    return bool(
        normalized_value
        and any(palabra in normalized_value for palabra in PALABRAS_DISPARO_REGISTRO)
    )


def es_salida_menu(
    text: Optional[str],
    opcion_menu: Optional[str] = None,
    *,
    opcion_salida: str = "5",
) -> bool:
    """Detecta si el texto o la opción piden volver al menú principal."""
    if str(opcion_menu or "").strip() == str(opcion_salida):
        return True

    normalized_value = normalizar_texto_interaccion(text)
    if not normalized_value:
        return False
    return any(palabra in normalized_value for palabra in SALIDA_MENU_PALABRAS)


def es_skip_value(
    text: Optional[str],
    selected_option: Optional[str] = None,
) -> bool:
    """Detecta valores de omisión universales para pasos opcionales."""
    option = normalizar_texto_interaccion(selected_option)
    if option in SKIP_VALUES_UNIVERSALES:
        return True

    normalized_value = normalizar_texto_interaccion(text)
    return bool(normalized_value and normalized_value in SKIP_VALUES_UNIVERSALES)


def normalizar_respuesta_binaria(
    text: Optional[str],
    afirmativas: Iterable[str],
    negativas: Iterable[str],
) -> Optional[bool]:
    """Interpreta una respuesta como afirmativa o negativa."""
    normalized_value = normalizar_texto_interaccion(text)
    if not normalized_value:
        return None

    afirmativas_norm = {str(item).strip().lower() for item in afirmativas if item}
    negativas_norm = {str(item).strip().lower() for item in negativas if item}

    if normalized_value in afirmativas_norm:
        return True
    if normalized_value in negativas_norm:
        return False
    return None


def interpretar_respuesta(text: Optional[str], modo: str = "menu") -> Optional[object]:
    """Interpretar respuesta del usuario unificando menú y consentimiento."""
    normalized_value = normalizar_texto_interaccion(text)
    if not normalized_value:
        return None

    if normalized_value.startswith("provider_menu_") or normalized_value.startswith(
        "provider_submenu_"
    ):
        return None

    if modo == "consentimiento":
        return normalizar_respuesta_binaria(
            normalized_value,
            RESPUESTAS_SI | RESPUESTAS_CONSENTIMIENTO_AFIRMATIVAS,
            RESPUESTAS_NO | RESPUESTAS_CONSENTIMIENTO_NEGATIVAS,
        )

    if modo == "menu":
        if (
            normalized_value.startswith("1")
            or normalized_value.startswith("uno")
            or "servicio" in normalized_value
            or "servicios" in normalized_value
            or "gestionar" in normalized_value
        ):
            return "1"

        if (
            normalized_value.startswith("2")
            or normalized_value.startswith("dos")
            or "selfie" in normalized_value
            or "foto" in normalized_value
            or "selfis" in normalized_value
            or "photo" in normalized_value
        ):
            return "2"

        if (
            normalized_value.startswith("3")
            or normalized_value.startswith("tres")
            or "red" in normalized_value
            or "social" in normalized_value
            or "instagram" in normalized_value
            or "facebook" in normalized_value
        ):
            return "3"

        if (
            normalized_value.startswith("4")
            or normalized_value.startswith("cuatro")
            or "eliminar" in normalized_value
            or "borrar" in normalized_value
            or "delete" in normalized_value
        ):
            return "4"

        if (
            normalized_value.startswith("5")
            or normalized_value.startswith("cinco")
            or "salir" in normalized_value
            or "terminar" in normalized_value
            or "menu" in normalized_value
            or "volver" in normalized_value
        ):
            return "5"

        return None

    return None
