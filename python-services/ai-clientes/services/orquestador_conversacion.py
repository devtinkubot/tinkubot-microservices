"""
Orquestador Conversacional - Coordina el flujo de conversación con clientes

Este módulo contiene la lógica de orquestación principal que procesa
mensajes de WhatsApp, maneja la máquina de estados y coordina con
otros servicios (disponibilidad, búsqueda, etc.).
"""

import asyncio
import logging
import os
import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, List, Optional

from flows.manejadores_estados import (
    procesar_estado_esperando_servicio,
    procesar_estado_esperando_ciudad,
)
from flows.configuracion import (
    GREETINGS,
    RESET_KEYWORDS,
    MAX_CONFIRM_ATTEMPTS,
    FAREWELL_MESSAGE,
)
from flows.enrutador import manejar_mensaje as manejar_mensaje_enrutador
from flows.enrutador import enrutar_estado as enrutar_estado_enrutador
from flows.mensajes import (
    mensaje_nueva_sesion_dict,
    mensaje_cuenta_suspendida_dict,
    mensaje_inicial_solicitud,
    mensaje_error_ciudad_no_reconocida,
    solicitar_ciudad_con_servicio,
    verificar_ciudad_y_proceder,
    mensajes_consentimiento,
)
from flows.validadores import validar_entrada_servicio
from flows.busqueda_proveedores.coordinador_busqueda import (
    coordinar_busqueda_completa,
    transicionar_a_busqueda_desde_ciudad,
)
from templates.mensajes.consentimiento import (
    opciones_consentimiento_textos,
)
from templates.mensajes.sesion import (
    mensaje_reinicio_por_inactividad,
)
from services.sesion_clientes import (
    validar_consentimiento,
    sincronizar_cliente,
    procesar_comando_reinicio,
)


# Constantes y configuración
SINONIMOS_CIUDADES_ECUADOR = {
    "Quito": {"quito", "quitsa", "kitsa", "kitu"},
    "Guayaquil": {"guayaquil", "gye"},
    "Cuenca": {"cuenca"},
    "Ambato": {"ambato"},
    "Riobamba": {"riobamba"},
    "Machala": {"machala"},
    "Loja": {"loja"},
    "Esmeraldas": {"esmeraldas"},
    "Manta": {"manta"},
    "Portoviejo": {"portoviejo"},
    "Santo Domingo": {"santo domingo", "santo domingo de los tsachilas"},
    "Ibarra": {"ibarra"},
    "Quevedo": {"quevedo"},
    "Valle": {"valle", "valle del chota"},
    "Babahoyo": {"babahoyo"},
    "Latacunga": {"latacunga"},
    "Salinas": {"salinas"},
}

PALABRAS_AFIRMATIVAS = {
    "si",
    "sí",
    "acepto",
    "claro",
    "correcto",
    "dale",
    "por supuesto",
    "asi es",
    "así es",
    "ok",
    "okay",
    "vale",
}

PALABRAS_NEGATIVAS = {
    "no",
    "nop",
    "cambio",
    "cambié",
    "otra",
    "otro",
    "negativo",
    "prefiero no",
}

USAR_EXTRACCION_IA = os.getenv("USE_AI_EXTRACTION", "true").lower() == "true"


def _normalizar_token(texto: str) -> str:
    texto_limpio = (texto or "").strip().lower()
    normalizado = unicodedata.normalize("NFD", texto_limpio)
    sin_acentos = "".join(
        ch for ch in normalizado if unicodedata.category(ch) != "Mn"
    )
    limpio = sin_acentos.replace("!", "").replace("?", "").replace(",", "")
    return limpio


def _normalizar_texto_para_coincidencia(texto: str) -> str:
    base = (texto or "").lower()
    normalizado = unicodedata.normalize("NFD", base)
    sin_acentos = "".join(
        ch for ch in normalizado if unicodedata.category(ch) != "Mn"
    )
    limpio = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", limpio).strip()


def normalizar_entrada_ciudad(texto: Optional[str]) -> Optional[str]:
    """Devuelve la ciudad canónica si coincide con la lista de ciudades de Ecuador."""
    if not texto:
        return None
    normalizado = _normalizar_texto_para_coincidencia(texto)
    if not normalizado:
        return None
    for ciudad_canonica, sinonimos in SINONIMOS_CIUDADES_ECUADOR.items():
        canonica_normalizada = _normalizar_texto_para_coincidencia(ciudad_canonica)
        if normalizado == canonica_normalizada:
            return ciudad_canonica
        for sinonimo in sinonimos:
            if normalizado == _normalizar_texto_para_coincidencia(sinonimo):
                return ciudad_canonica
    return None


def interpretar_si_no(texto: Optional[str]) -> Optional[bool]:
    if not texto:
        return None
    base = _normalizar_token(texto)
    if not base:
        return None
    tokens = base.split()
    afirmativos_normalizados = {_normalizar_token(word) for word in PALABRAS_AFIRMATIVAS}
    negativos_normalizados = {_normalizar_token(word) for word in PALABRAS_NEGATIVAS}

    if base in afirmativos_normalizados:
        return True
    if base in negativos_normalizados:
        return False

    for token in tokens:
        if token in afirmativos_normalizados:
            return True
        if token in negativos_normalizados:
            return False
    return None


def extraer_servicio_y_ubicacion(
    historial_texto: str, ultimo_mensaje: str
) -> tuple[Optional[str], Optional[str]]:
    """
    Extrae ubicación (ciudad) del texto con heurística local.

    La extracción de servicio se resuelve con IA en el extractor canónico.
    Esta función mantiene compatibilidad para detección de ciudad en texto libre.
    """
    texto_combinado = f"{historial_texto}\n{ultimo_mensaje}"
    texto_normalizado = _normalizar_texto_para_coincidencia(texto_combinado)
    if not texto_normalizado:
        return None, None

    texto_con_padding = f" {texto_normalizado} "

    # Servicio siempre es None - se extrae con IA
    profesion = None

    ubicacion = None
    for ciudad_canonica, sinonimos in SINONIMOS_CIUDADES_ECUADOR.items():
        canonica_normalizada = _normalizar_texto_para_coincidencia(ciudad_canonica)
        if f" {canonica_normalizada} " in texto_con_padding:
            ubicacion = ciudad_canonica
            break
        for sinonimo in sinonimos:
            sinonimo_normalizado = _normalizar_texto_para_coincidencia(sinonimo)
            if f" {sinonimo_normalizado} " in texto_con_padding:
                ubicacion = ciudad_canonica
                break
        if ubicacion:
            break

    return profesion, ubicacion


def normalizar_boton(valor: Optional[str]) -> Optional[str]:
    """Normaliza el valor de un botón/quick reply para comparaciones robustas."""
    if not valor:
        return None
    return valor.strip().strip("*").rstrip(".)")


class OrquestadorConversacional:
    """
    Orquesta el flujo de conversación con clientes.

    Responsabilidades:
    - Validar consentimiento
    - Manejar inactividad
    - Coordinar máquina de estados
    - Ejecutar búsquedas con verificación de disponibilidad
    - Persistir estado y sesiones
    """

    def __init__(
        self,
        redis_client,
        supabase,
        gestor_sesiones,
        buscador=None,
        validador=None,
        extractor_ia=None,
        servicio_consentimiento=None,
        repositorio_flujo=None,
        repositorio_clientes=None,
        logger=None,
    ):
        """
        Inicializar orquestador con dependencias.

        Args:
            redis_client: Cliente Redis para persistencia de flujo
            supabase: Cliente Supabase para datos de clientes
            gestor_sesiones: Gestor de sesiones para historial
            buscador: Servicio BuscadorProveedores (opcional, para backward compatibility)
            validador: Servicio ValidadorProveedoresIA (opcional, para backward compatibility)
            extractor_ia: Servicio ExtractorNecesidadIA (requerido)
            servicio_consentimiento: Servicio ServicioConsentimiento (opcional, para backward compatibility)
            repositorio_flujo: RepositorioFlujoRedis (opcional, para backward compatibility)
            repositorio_clientes: RepositorioClientesSupabase (opcional, para backward compatibility)
            logger: Logger opcional (usa __name__ si None)
        """
        self.redis_client = redis_client
        self.supabase = supabase
        self.gestor_sesiones = gestor_sesiones
        self.logger = logger or logging.getLogger(__name__)
        if extractor_ia is None:
            raise ValueError("extractor_ia es obligatorio en OrquestadorConversacional")

        # Nuevos servicios (inyectados opcionalmente para backward compatibility)
        self.buscador = buscador
        self.validador = validador
        self.extractor_ia = extractor_ia
        self.servicio_consentimiento = servicio_consentimiento
        self.repositorio_flujo = repositorio_flujo
        self.repositorio_clientes = repositorio_clientes

        # Constantes/config usadas por el router
        self.greetings = GREETINGS
        self.usar_extraccion_ia = USAR_EXTRACCION_IA
        self.farewell_message = FAREWELL_MESSAGE
        self.max_confirm_attempts = MAX_CONFIRM_ATTEMPTS
        # Nombres en español para extracción de servicio
        self.extraer_servicio_y_ubicacion = extraer_servicio_y_ubicacion

        # Inyectar callbacks necesarios
        self._setup_callbacks()

    def _setup_callbacks(self):
        """
        Configura callbacks para funciones auxiliares.

        NOTA: Estas funciones deben inyectarse desde main.py después de instanciar
        el orquestador para evitar dependencias circulares.

        Si los nuevos servicios están inyectados, los callbacks usarán los servicios.
        Si no, se mantienen los callbacks globales para backward compatibility.
        """
        # Los callbacks se inyectan desde main.py, pero si tenemos los nuevos servicios
        # podemos usarlos directamente en lugar de depender de callbacks globales
        pass

    def inyectar_callbacks(self, **callbacks):
        """
        Inyecta callbacks desde main.py para evitar dependencias circulares.

        Args:
            **callbacks: Dict con las funciones a inyectar:
                - obtener_o_crear_cliente
                - solicitar_consentimiento
                - manejar_respuesta_consentimiento
                - resetear_flujo
                - obtener_flujo
                - guardar_flujo
                - actualizar_ciudad_cliente
                - verificar_si_bloqueado
                - validar_contenido_con_ia
                - buscar_proveedores
                - enviar_prompt_proveedor
                - enviar_prompt_confirmacion
                - limpiar_ciudad_cliente
                - limpiar_consentimiento_cliente
                - mensaje_conexion_formal
                - programar_solicitud_retroalimentacion
                - enviar_texto_whatsapp
        """
        for name, func in callbacks.items():
            setattr(self, name, func)

    async def procesar_mensaje_whatsapp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Punto de entrada principal que procesa un mensaje de WhatsApp.

        Flujo:
        1. Valida consentimiento del usuario
        2. Maneja inactividad (>3 min)
        3. Sincroniza perfil de cliente
        4. Extrae entidad (profesión, ciudad)
        5. Ejecuta máquina de estados según estado actual
        6. Persiste flujo y guarda sesión

        Args:
            payload: Dict con from_number, content, selected_option, message_type, location

        Returns:
            Dict con "response" o "messages" para enviar a WhatsApp
        """
        return await manejar_mensaje_enrutador(self, payload)

    async def _validar_consentimiento(
        self, telefono: str, perfil_cliente: Dict[str, Any], carga: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Maneja el flujo de validación de consentimiento."""
        return await validar_consentimiento(
            telefono=telefono,
            perfil_cliente=perfil_cliente,
            carga=carga,
            servicio_consentimiento=self.servicio_consentimiento,
            manejar_respuesta_consentimiento=self.manejar_respuesta_consentimiento,
            solicitar_consentimiento=self.solicitar_consentimiento,
            normalizar_boton_fn=normalizar_boton,
            interpretar_si_no_fn=interpretar_si_no,
            opciones_consentimiento_textos=opciones_consentimiento_textos,
        )

    async def _sincronizar_cliente(
        self, flujo: Dict[str, Any], perfil_cliente: Dict[str, Any]
    ) -> Optional[str]:
        """Sincroniza el perfil del cliente con el flujo."""
        return await sincronizar_cliente(
            flujo=flujo,
            perfil_cliente=perfil_cliente,
            logger=self.logger,
        )

    def _extraer_datos_mensaje(self, carga: Dict[str, Any]) -> tuple:
        """Extrae y normaliza datos del mensaje."""
        texto = (carga.get("content") or "").strip()
        seleccionado = normalizar_boton(carga.get("selected_option"))
        tipo_mensaje = carga.get("message_type")
        ubicacion = carga.get("location") or {}
        return texto, seleccionado, tipo_mensaje, ubicacion

    async def _detectar_y_actualizar_ciudad(
        self,
        flujo: Dict[str, Any],
        texto: str,
        cliente_id: Optional[str],
        perfil_cliente: Dict[str, Any],
    ):
        """Detecta ciudad en el texto y la actualiza si es necesario."""
        profesion_detectada, ciudad_detectada = extraer_servicio_y_ubicacion("", texto)
        if ciudad_detectada:
            ciudad_normalizada = ciudad_detectada
            ciudad_actual = (flujo.get("city") or "").strip()
            if ciudad_normalizada.lower() != ciudad_actual.lower():
                # Usar repositorio si está disponible, sino callback
                if self.repositorio_clientes:
                    perfil_actualizado = await self.repositorio_clientes.actualizar_ciudad(
                        flujo.get("customer_id") or cliente_id,
                        ciudad_normalizada,
                    )
                else:
                    perfil_actualizado = await self.actualizar_ciudad_cliente(
                        flujo.get("customer_id") or cliente_id,
                        ciudad_normalizada,
                    )
                if perfil_actualizado:
                    perfil_cliente = perfil_actualizado
                    flujo["city"] = perfil_actualizado.get("city")
                    flujo["city_confirmed"] = True
                    flujo["city_confirmed_at"] = perfil_actualizado.get("city_confirmed_at")
                    cliente_id = perfil_actualizado.get("id")
                    flujo["customer_id"] = cliente_id
                else:
                    flujo["city"] = ciudad_normalizada
                    flujo["city_confirmed"] = True
            else:
                flujo["city_confirmed"] = True

    async def _procesar_comando_reinicio(
        self, telefono: str, flujo: Dict[str, Any], texto: str
    ) -> Optional[Dict[str, Any]]:
        """Procesa comandos de reinicio de flujo."""
        return await procesar_comando_reinicio(
            telefono=telefono,
            flujo=flujo,
            texto=texto,
            repositorio_flujo=self.repositorio_flujo,
            resetear_flujo=self.resetear_flujo,
            guardar_flujo=self.guardar_flujo,
            repositorio_clientes=self.repositorio_clientes,
            limpiar_ciudad_cliente=self.limpiar_ciudad_cliente,
            limpiar_consentimiento_cliente=self.limpiar_consentimiento_cliente,
            mensaje_nueva_sesion_dict=mensaje_nueva_sesion_dict,
            reset_keywords=RESET_KEYWORDS,
        )

    async def _procesar_estado(
        self,
        telefono: str,
        flujo: Dict[str, Any],
        texto: str,
        seleccionado: Optional[str],
        tipo_mensaje: str,
        ubicacion: Dict[str, Any],
        cliente_id: Optional[str],
    ) -> Dict[str, Any]:
        """
        Procesa el mensaje según el estado actual de la máquina de estados.
        """
        return await enrutar_estado_enrutador(
            self,
            telefono=telefono,
            flujo=flujo,
            texto=texto,
            seleccionado=seleccionado,
            tipo_mensaje=tipo_mensaje,
            ubicacion=ubicacion,
            cliente_id=cliente_id,
        )

    async def _procesar_awaiting_service(
        self,
        telefono: str,
        flujo: Dict[str, Any],
        texto: str,
        responder,
        cliente_id: Optional[str],
    ) -> Dict[str, Any]:
        """Procesa el estado 'awaiting_service'."""
        # 0. Verificar si está baneado
        if await self.verificar_si_bloqueado(telefono):
            return await responder(
                flujo, {"response": mensaje_cuenta_suspendida_dict()["response"]}
            )

        # 1. Validación estructurada básica
        # NOTA: Ya no usamos catálogo estático de servicios - IA detecta cualquier servicio
        es_valido, mensaje_error = validar_entrada_servicio(
            texto or "", GREETINGS, {}  # Catálogo vacío - IA detecta servicios dinámicamente
        )

        if not es_valido:
            return await responder(flujo, {"response": mensaje_error})

        # 2. Validación IA de contenido
        mensaje_advertencia, mensaje_ban = await self.validar_contenido_con_ia(
            texto or "", telefono
        )

        if mensaje_ban:
            return await responder(flujo, {"response": mensaje_ban})

        if mensaje_advertencia:
            return await responder(flujo, {"response": mensaje_advertencia})

        # 3. IA-only extraction (implementación canónica)
        funcion_extraccion = self.extractor_ia.extraer_servicio_con_ia_pura

        flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
            flujo,
            texto,
            GREETINGS,
            mensaje_inicial_solicitud(),
            funcion_extraccion,
        )
        flujo = flujo_actualizado

        if flujo.get("state") == "confirm_service":
            return await responder(flujo, respuesta)

        # 4. Verificar ciudad existente (optimización)
        # Usar repositorio si está disponible, sino callback
        if self.repositorio_clientes:
            perfil_cliente = await self.repositorio_clientes.obtener_o_crear(
                telefono=telefono
            )
        else:
            perfil_cliente = await self.obtener_o_crear_cliente(telefono)
        respuesta_ciudad = await verificar_ciudad_y_proceder(flujo, perfil_cliente)

        # 5. Si tiene ciudad, disparar búsqueda
        if flujo.get("state") == "searching":
            mensaje_confirmacion = await coordinar_busqueda_completa(
                telefono=telefono,
                flujo=flujo,
                enviar_mensaje_callback=self.enviar_texto_whatsapp,
                guardar_flujo_callback=self.guardar_flujo,
            )
            mensajes = []
            if respuesta_ciudad.get("response"):
                mensajes.append({"response": respuesta_ciudad["response"]})
            if mensaje_confirmacion:
                mensajes.append({"response": mensaje_confirmacion})
            return {"messages": mensajes}

        # 6. Si no tiene ciudad, pedir normalmente
        return await responder(flujo, respuesta_ciudad)

    async def _procesar_awaiting_city(
        self,
        telefono: str,
        flujo: Dict[str, Any],
        texto: str,
        responder,
        guardar_mensaje_bot,
    ) -> Dict[str, Any]:
        """Procesa el estado 'awaiting_city'."""
        cliente_id = flujo.get("customer_id")
        # Usar repositorio si está disponible, sino callback
        if self.repositorio_clientes:
            perfil_cliente = await self.repositorio_clientes.obtener_o_crear(
                telefono=telefono
            )
        else:
            perfil_cliente = await self.obtener_o_crear_cliente(telefono)

        # Si no hay servicio previo y el usuario escribe un servicio aquí, reencaminarlo
        if texto and not flujo.get("service"):
            profesion_detectada, ciudad_detectada = extraer_servicio_y_ubicacion(
                "", texto
            )
            servicio_actual_norm = _normalizar_texto_para_coincidencia(
                flujo.get("service") or ""
            )
            nuevo_servicio_norm = _normalizar_texto_para_coincidencia(
                profesion_detectada or texto or ""
            )
            if profesion_detectada and nuevo_servicio_norm != servicio_actual_norm:
                for key in [
                    "providers",
                    "chosen_provider",
                    "provider_detail_idx",
                    "city",
                    "city_confirmed",
                    "searching_dispatched",
                    "searching_started_at",  # NUEVO: limpiar timestamp de búsqueda
                ]:
                    flujo.pop(key, None)
                valor_servicio = (profesion_detectada or "").strip()
                if not valor_servicio:
                    return await responder(
                        flujo,
                        {
                            "response": (
                                "No pude identificar el servicio con claridad. "
                                "Por favor descríbelo nuevamente antes de indicar la ciudad."
                            )
                        },
                    )
                flujo.update(
                    {
                        "service": valor_servicio,
                        "service_full": texto,
                        "state": "awaiting_city",
                        "city_confirmed": False,
                    }
                )
                # Usar repositorio si está disponible, sino callback
                if self.repositorio_flujo:
                    await self.repositorio_flujo.guardar(telefono, flujo)
                else:
                    await self.guardar_flujo(telefono, flujo)
                return await responder(
                    flujo,
                    solicitar_ciudad_con_servicio(valor_servicio),
                )

        ciudad_normalizada_entrada = normalizar_entrada_ciudad(texto)
        if texto and not ciudad_normalizada_entrada:
            return await responder(
                flujo,
                mensaje_error_ciudad_no_reconocida(),
            )

        from templates.mensajes.ubicacion import solicitar_ciudad_formato

        flujo_actualizado, respuesta = procesar_estado_esperando_ciudad(
            flujo,
            ciudad_normalizada_entrada or texto,
            solicitar_ciudad_formato(),
        )

        if texto:
            entrada_normalizada = (ciudad_normalizada_entrada or texto).strip().title()
            flujo_actualizado["city"] = entrada_normalizada
            flujo_actualizado["city_confirmed"] = True
            # Usar repositorio si está disponible, sino callback
            if self.repositorio_clientes:
                resultado_actualizacion = await self.repositorio_clientes.actualizar_ciudad(
                    flujo_actualizado.get("customer_id") or cliente_id,
                    entrada_normalizada,
                )
            else:
                resultado_actualizacion = await self.actualizar_ciudad_cliente(
                    flujo_actualizado.get("customer_id") or cliente_id,
                    entrada_normalizada,
                )
            if resultado_actualizacion:
                flujo_actualizado["city_confirmed_at"] = resultado_actualizacion.get(
                    "city_confirmed_at"
                )

        if respuesta.get("response"):
            return await responder(flujo_actualizado, respuesta)

        if not flujo_actualizado.get("service"):
            flujo_actualizado["state"] = "awaiting_service"
            return await responder(
                flujo_actualizado,
                {"response": mensaje_inicial_solicitud()},
            )

        # Usar transicionar_a_busqueda_desde_ciudad
        ciudad_del_flujo = flujo_actualizado.get("city") or (
            ciudad_normalizada_entrada or texto
        ).strip().title()
        resultado = await transicionar_a_busqueda_desde_ciudad(
            telefono=telefono,
            flujo=flujo_actualizado,
            ciudad_normalizada=ciudad_del_flujo,
            cliente_id=flujo_actualizado.get("customer_id") or cliente_id,
            # Usar repositorio si está disponible, sino callback
            actualizar_ciudad_cliente_callback=(
                self.repositorio_clientes.actualizar_ciudad
                if self.repositorio_clientes
                else self.actualizar_ciudad_cliente
            ),
            enviar_mensaje_callback=self.enviar_texto_whatsapp,
            guardar_flujo_callback=(
                self.repositorio_flujo.guardar
                if self.repositorio_flujo
                else self.guardar_flujo
            ),
        )
        # Guardar mensaje en sesión si existe response
        if resultado.get("messages") and resultado["messages"][0].get("response"):
            await guardar_mensaje_bot(resultado["messages"][0]["response"])
        return resultado

    async def _procesar_searching(
        self, telefono: str, flujo: Dict[str, Any], ejecutar_busqueda
    ) -> Dict[str, Any]:
        """Procesa el estado 'searching' con timeout para búsquedas fallidas."""
        SEARCHING_TIMEOUT_SECONDS = 60

        if flujo.get("searching_dispatched"):
            searching_started_at = flujo.get("searching_started_at")

            if searching_started_at:
                try:
                    from datetime import datetime
                    ahora_utc = datetime.utcnow()
                    inicio_dt = datetime.fromisoformat(searching_started_at)
                    segundos_transcurridos = (ahora_utc - inicio_dt).total_seconds()

                    if segundos_transcurridos > SEARCHING_TIMEOUT_SECONDS:
                        self.logger.warning(
                            f"⏰ TIMEOUT de búsqueda detectado para {telefono}: "
                            f"{segundos_transcurridos:.1f}s transcurridos"
                        )

                        # Restablecer estado
                        flujo["searching_dispatched"] = False
                        flujo.pop("searching_started_at", None)

                        if self.repositorio_flujo:
                            await self.repositorio_flujo.guardar(telefono, flujo)
                        else:
                            await self.guardar_flujo(telefono, flujo)

                        return {
                            "response": (
                                f"⚠️ La búsqueda tomó demasiado tiempo. "
                                f"Por favor intenta nuevamente."
                            )
                        }
                except Exception as e:
                    self.logger.error(f"❌ Error verificando timeout: {e}")
                    flujo["searching_dispatched"] = False
                    flujo.pop("searching_started_at", None)
                    if self.repositorio_flujo:
                        await self.repositorio_flujo.guardar(telefono, flujo)
                    else:
                        await self.guardar_flujo(telefono, flujo)

            return {
                "response": f"Estoy buscando {flujo.get('service')} en {flujo.get('city')}, espera un momento."
            }

        # Si no se despachó, lanzarla ahora
        if flujo.get("service") and flujo.get("city"):
            mensaje_confirmacion = await coordinar_busqueda_completa(
                telefono=telefono,
                flujo=flujo,
                enviar_mensaje_callback=self.enviar_texto_whatsapp,
                guardar_flujo_callback=self.guardar_flujo,
            )
            return {"response": mensaje_confirmacion or "Iniciando búsqueda..."}

        return await ejecutar_busqueda()
