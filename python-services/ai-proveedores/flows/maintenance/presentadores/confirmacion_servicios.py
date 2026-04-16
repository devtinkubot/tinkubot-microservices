"""Presentación de mensajes para confirmación y edición de servicios."""

from typing import Any, Dict, List, Optional

from templates.maintenance import (
    mensaje_correccion_servicios,
    payload_confirmacion_resumen,
)
from templates.maintenance.mensajes_servicios import (
    mensaje_confirmar_o_corregir_servicio,
    mensaje_limite_servicios_temporales,
    mensaje_servicio_ya_existe_en_lista,
)
from templates.maintenance.menus import (
    payload_detalle_servicios,
)
from templates.maintenance.registration import (
    construir_resumen_confirmacion_perfil_profesional,
    mensaje_debes_registrar_al_menos_un_servicio,
    mensaje_debes_registrar_mas_servicios,
    mensaje_error_opcion_agregar_otro,
    mensaje_menu_edicion_perfil_profesional,
    mensaje_menu_edicion_servicios_registro,
    mensaje_resumen_servicios_registro,
    mensaje_servicio_actualizado,
    mensaje_servicio_eliminado_registro,
    payload_certificado_opcional,
    payload_menu_edicion_servicios_registro,
    payload_red_social_opcional,
    preguntar_experiencia_general,
    preguntar_nuevo_servicio_reemplazo,
    preguntar_numero_servicio_eliminar,
    preguntar_numero_servicio_reemplazar,
    preguntar_siguiente_servicio_registro,
)
from templates.shared import mensaje_perfecto_guardar_perfil_profesional


class PresentadorConfirmacion:
    def payload_resumen_perfil(self, flujo: Dict[str, Any]) -> Dict[str, Any]:
        return payload_confirmacion_resumen(
            construir_resumen_confirmacion_perfil_profesional(
                experience_range=flujo.get("experience_range"),
                facebook_username=flujo.get("facebook_username"),
                instagram_username=flujo.get("instagram_username"),
                certificate_uploaded=bool(flujo.get("certificate_uploaded")),
                services=list(flujo.get("servicios_temporales") or []),
            )
        )

    def respuesta_confirmar_o_corregir_servicio(self) -> Dict[str, Any]:
        return {"response": mensaje_confirmar_o_corregir_servicio()}

    def respuesta_perfecto_guardar_perfil(self) -> Dict[str, Any]:
        return {"response": mensaje_perfecto_guardar_perfil_profesional()}

    def respuesta_menu_edicion_perfil(self) -> Dict[str, Any]:
        return {"response": mensaje_menu_edicion_perfil_profesional()}

    def respuesta_preguntar_experiencia(self) -> Dict[str, Any]:
        return {"response": preguntar_experiencia_general()}

    def respuesta_red_social_opcional(self) -> Dict[str, Any]:
        return payload_red_social_opcional()

    def respuesta_certificado_opcional(self) -> Dict[str, Any]:
        return payload_certificado_opcional()

    def respuesta_preguntar_siguiente_servicio(
        self,
        indice: int,
        maximo_visible: int,
        minimo_perfil: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "response": preguntar_siguiente_servicio_registro(
                indice,
                maximo_visible,
                minimo_perfil,
            )
        }

    def respuesta_resumen_servicios_registro(
        self,
        servicios: List[str],
        maximo_visible: int,
    ) -> Dict[str, Any]:
        return {
            "response": mensaje_resumen_servicios_registro(
                servicios,
                maximo_visible,
            )
        }

    def respuesta_error_opcion_agregar_otro(self) -> Dict[str, Any]:
        return {"response": mensaje_error_opcion_agregar_otro()}

    def respuesta_debes_registrar_al_menos_un_servicio(self) -> Dict[str, Any]:
        return {"response": mensaje_debes_registrar_al_menos_un_servicio()}

    def respuesta_debes_registrar_mas_servicios(
        self,
        minimo: int,
    ) -> Dict[str, Any]:
        return {"response": mensaje_debes_registrar_mas_servicios(minimo)}

    def respuesta_correccion_servicios(self) -> Dict[str, Any]:
        return {"response": mensaje_correccion_servicios()}

    def respuesta_mensaje_edicion_servicios_registro(
        self,
        servicios: List[str],
        maximo_visible: int,
    ) -> Dict[str, Any]:
        return {
            "response": mensaje_menu_edicion_servicios_registro(
                servicios,
                maximo_visible,
            )
        }

    def respuesta_payload_detalle_servicios(
        self,
        servicios: List[str],
        maximo_visible: int,
    ) -> Dict[str, Any]:
        return payload_detalle_servicios(servicios, maximo_visible)

    def respuesta_payload_menu_edicion_servicios_registro(
        self,
        servicios: List[str],
        maximo_visible: int,
    ) -> Dict[str, Any]:
        return payload_menu_edicion_servicios_registro(servicios, maximo_visible)

    def respuesta_preguntar_numero_servicio_eliminar(self) -> Dict[str, Any]:
        return {"response": preguntar_numero_servicio_eliminar()}

    def respuesta_preguntar_numero_servicio_reemplazar(self) -> Dict[str, Any]:
        return {"response": preguntar_numero_servicio_reemplazar()}

    def respuesta_preguntar_nuevo_servicio_reemplazo(
        self,
        indice: int,
        servicio_actual: str,
    ) -> Dict[str, Any]:
        return {
            "response": preguntar_nuevo_servicio_reemplazo(
                indice,
                servicio_actual,
            )
        }

    def respuesta_mensaje_servicio_actualizado(self, nuevo: str) -> Dict[str, Any]:
        return {"response": mensaje_servicio_actualizado(nuevo)}

    def respuesta_mensaje_servicio_eliminado(self, eliminado: str) -> Dict[str, Any]:
        return {"response": mensaje_servicio_eliminado_registro(eliminado)}

    def respuesta_mensaje_limite_temporal(
        self,
        maximo_visible: int,
        perfil_completo: bool,
    ) -> Dict[str, Any]:
        return {
            "response": mensaje_limite_servicios_temporales(
                maximo_visible,
                perfil_completo,
            )
        }

