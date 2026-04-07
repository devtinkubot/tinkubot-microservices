"""
Orquestador Conversacional - Coordina el flujo de conversación con clientes

Este módulo contiene la lógica de orquestación principal que procesa
mensajes de WhatsApp, maneja la máquina de estados y coordina con
otros servicios (disponibilidad, búsqueda, etc.).
"""

import asyncio
import logging
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import httpx

from contracts.repositorios import IRepositorioClientes, IRepositorioFlujo
from flows.busqueda_proveedores.coordinador_busqueda import (
    coordinar_busqueda_completa,
    transicionar_a_busqueda_desde_ciudad,
)
from flows.configuracion import (
    FAREWELL_MESSAGE,
    GREETINGS,
    MAX_CONFIRM_ATTEMPTS,
    RESET_KEYWORDS,
)
from flows.enrutador import enrutar_estado as enrutar_estado_enrutador
from flows.enrutador import manejar_mensaje as manejar_mensaje_enrutador
from flows.manejadores_estados import (
    procesar_estado_esperando_ciudad,
    procesar_estado_esperando_servicio,
)
from flows.mensajes import (
    mensaje_cuenta_suspendida_dict,
    mensaje_error_ciudad_no_reconocida,
    mensaje_inicial_solicitud,
    mensaje_nueva_sesion_dict,
    solicitar_ciudad_con_servicio,
    verificar_ciudad_y_proceder,
)
from flows.validadores import validar_entrada_servicio
from infrastructure.database import run_supabase
from services.sesion_clientes import (
    procesar_comando_reinicio,
    sincronizar_cliente,
    validar_consentimiento,
)
from templates.mensajes.consentimiento import (
    opciones_consentimiento_textos,
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

GEOCODING_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 días
GEOCODING_COORD_PRECISION = 4
GEOCODING_TIMEOUT_SECONDS = 2.5
GEOCODING_MAX_RETRIES = 1
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "tinkubot-ai-clientes/1.0 (support@tinkubot.com)"


def _normalizar_token(texto: str) -> str:
    texto_limpio = (texto or "").strip().lower()
    normalizado = unicodedata.normalize("NFD", texto_limpio)
    sin_acentos = "".join(ch for ch in normalizado if unicodedata.category(ch) != "Mn")
    limpio = sin_acentos.replace("!", "").replace("?", "").replace(",", "")
    return limpio


def _normalizar_texto_para_coincidencia(texto: str) -> str:
    base = (texto or "").lower()
    normalizado = unicodedata.normalize("NFD", base)
    sin_acentos = "".join(ch for ch in normalizado if unicodedata.category(ch) != "Mn")
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


def _resolver_ciudad_canton_desde_texto(texto: Optional[str]) -> Optional[str]:
    """Resuelve una ciudad/cantón canónico desde texto libre o metadatos."""
    ciudad_directa = normalizar_entrada_ciudad(texto)
    if ciudad_directa:
        return ciudad_directa
    _, ciudad_detectada = extraer_servicio_y_ubicacion("", texto or "")
    return ciudad_detectada


def interpretar_si_no(texto: Optional[str]) -> Optional[bool]:
    if not texto:
        return None
    base = _normalizar_token(texto)
    if not base:
        return None
    tokens = base.split()
    afirmativos_normalizados = {
        _normalizar_token(word) for word in PALABRAS_AFIRMATIVAS
    }
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


def _parsear_coordenada(valor: Any) -> Optional[float]:
    """Convierte una coordenada a float de forma segura."""
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def extraer_ciudad_desde_payload_ubicacion(
    ubicacion: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Intenta inferir ciudad desde metadatos de ubicación recibidos por WhatsApp."""
    if not isinstance(ubicacion, dict):
        return None

    if isinstance(ubicacion.get("city"), str) and ubicacion["city"].strip():
        ciudad_directa = _resolver_ciudad_canton_desde_texto(ubicacion["city"])
        if ciudad_directa:
            return ciudad_directa

    candidatos = [
        ubicacion.get("address"),
        ubicacion.get("name"),
    ]
    texto = " ".join(
        parte.strip() for parte in candidatos if isinstance(parte, str) and parte.strip()
    )
    if not texto:
        return None
    return _resolver_ciudad_canton_desde_texto(texto)


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
        repositorio_flujo: Optional[IRepositorioFlujo] = None,
        repositorio_clientes: Optional[IRepositorioClientes] = None,
        logger=None,
    ):
        """
        Inicializar orquestador con dependencias.

        Args:
            redis_client: Cliente Redis para persistencia de flujo
            supabase: Cliente Supabase para datos de clientes
            gestor_sesiones: Gestor de sesiones para historial
            buscador: Servicio BuscadorProveedores
                (opcional, para backward compatibility)
            validador: Servicio ValidadorProveedoresIA
                (opcional, para backward compatibility)
            extractor_ia: Servicio ExtractorNecesidadIA (requerido)
            servicio_consentimiento: Servicio ServicioConsentimiento
                (opcional, para backward compatibility)
            repositorio_flujo: RepositorioFlujoRedis
                (opcional, para backward compatibility)
            repositorio_clientes: RepositorioClientesSupabase
                (opcional, para backward compatibility)
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
                - limpiar_ubicacion_cliente
                - limpiar_consentimiento_cliente
                - mensaje_conexion_formal
                - preparar_proveedor_para_detalle
                - programar_solicitud_retroalimentacion
                - enviar_texto_whatsapp
        """
        for name, func in callbacks.items():
            setattr(self, name, func)

    async def procesar_mensaje_whatsapp(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
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
            payload: Dict con from_number, content, selected_option, message_type,
                location

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

    async def obtener_servicios_populares_recientes(self, limite: int = 5) -> list[str]:
        """Obtiene servicios más solicitados en los últimos 30 días."""
        if not self.supabase:
            return []
        try:
            desde = (datetime.utcnow() - timedelta(days=30)).isoformat()
            respuesta = await run_supabase(
                lambda: self.supabase.table("lead_events")
                .select("service,created_at")
                .gte("created_at", desde)
                .order("created_at", desc=True)
                .limit(500)
                .execute(),
                etiqueta="lead_events.popular_30d",
            )
            filas = respuesta.data or []
            conteo: Dict[str, int] = {}
            etiqueta_por_clave: Dict[str, str] = {}
            for fila in filas:
                servicio = ((fila or {}).get("service") or "").strip()
                if not servicio:
                    continue
                clave = servicio.lower()
                conteo[clave] = conteo.get(clave, 0) + 1
                etiqueta_por_clave.setdefault(clave, servicio)
            ordenadas = sorted(
                conteo.items(),
                key=lambda item: (-item[1], item[0]),
            )
            return [etiqueta_por_clave[k] for k, _ in ordenadas[:limite]]
        except Exception as exc:
            self.logger.warning("No se pudo obtener servicios populares: %s", exc)
            return []

    async def construir_prompt_inicial_servicio(self) -> Dict[str, Any]:
        """Construye payload inicial de servicio con lista interactiva."""
        from templates.mensajes.validacion import construir_prompt_lista_servicios

        servicios = await self.obtener_servicios_populares_recientes(limite=5)
        return construir_prompt_lista_servicios(servicios)

    async def _obtener_ciudad_cache_geocoding(
        self, latitud: float, longitud: float
    ) -> Optional[str]:
        """Obtiene ciudad resuelta desde cache Redis si existe."""
        if not self.redis_client:
            return None

        cache_key = (
            f"geo:rev:{latitud:.{GEOCODING_COORD_PRECISION}f}:"
            f"{longitud:.{GEOCODING_COORD_PRECISION}f}"
        )
        try:
            cache_valor = await self.redis_client.get(cache_key)
        except Exception as exc:
            self.logger.warning(
                "⚠️ geocode_cache_read_error key=%s error=%s",
                cache_key,
                exc,
            )
            return None

        if not cache_valor:
            return None

        ciudad_cache = None
        if isinstance(cache_valor, dict):
            ciudad_cache = cache_valor.get("city")
        elif isinstance(cache_valor, str):
            ciudad_cache = cache_valor

        ciudad_normalizada = normalizar_entrada_ciudad(ciudad_cache)
        if ciudad_normalizada:
            self.logger.info(
                "📦 geocode_cache_hit key=%s city=%s",
                cache_key,
                ciudad_normalizada,
            )
        return ciudad_normalizada

    async def _guardar_ciudad_cache_geocoding(
        self, latitud: float, longitud: float, ciudad: str
    ) -> None:
        """Guarda ciudad resuelta en cache Redis."""
        if not self.redis_client:
            return
        cache_key = (
            f"geo:rev:{latitud:.{GEOCODING_COORD_PRECISION}f}:"
            f"{longitud:.{GEOCODING_COORD_PRECISION}f}"
        )
        try:
            await self.redis_client.set(
                cache_key,
                {"city": ciudad, "provider": "nominatim"},
                expire=GEOCODING_CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            self.logger.warning(
                "⚠️ geocode_cache_write_error key=%s error=%s",
                cache_key,
                exc,
            )

    async def _resolver_ciudad_desde_coordenadas(
        self, latitud: float, longitud: float
    ) -> Optional[str]:
        """Resuelve ciudad desde lat/lng usando reverse geocoding."""
        ciudad_cache = await self._obtener_ciudad_cache_geocoding(latitud, longitud)
        if ciudad_cache:
            return ciudad_cache

        params = {
            "format": "jsonv2",
            "lat": latitud,
            "lon": longitud,
            "zoom": 10,
            "addressdetails": 1,
            "accept-language": "es",
        }
        headers = {"User-Agent": NOMINATIM_USER_AGENT}
        timeout = httpx.Timeout(GEOCODING_TIMEOUT_SECONDS)

        for intento in range(1, GEOCODING_MAX_RETRIES + 2):
            try:
                self.logger.info(
                    "🌐 geocode_provider_call provider=nominatim attempt=%s lat=%s lng=%s",
                    intento,
                    latitud,
                    longitud,
                )
                async with httpx.AsyncClient(timeout=timeout) as client:
                    respuesta = await client.get(
                        NOMINATIM_REVERSE_URL, params=params, headers=headers
                    )
                if respuesta.status_code != 200:
                    self.logger.warning(
                        "⚠️ geocode_provider_status provider=nominatim attempt=%s status=%s",
                        intento,
                        respuesta.status_code,
                    )
                    continue

                payload = respuesta.json()
                direccion = payload.get("address") or {}
                candidatos = [
                    direccion.get("city"),
                    direccion.get("town"),
                    direccion.get("village"),
                    direccion.get("county"),
                    direccion.get("municipality"),
                ]
                for candidato in candidatos:
                    ciudad_normalizada = normalizar_entrada_ciudad(candidato)
                    if ciudad_normalizada:
                        await self._guardar_ciudad_cache_geocoding(
                            latitud, longitud, ciudad_normalizada
                        )
                        return ciudad_normalizada

                display_name = payload.get("display_name") or ""
                _, ciudad_display = extraer_servicio_y_ubicacion("", display_name)
                if ciudad_display:
                    await self._guardar_ciudad_cache_geocoding(
                        latitud, longitud, ciudad_display
                    )
                    return ciudad_display
            except Exception as exc:
                self.logger.warning(
                    "⚠️ geocode_provider_timeout provider=nominatim attempt=%s error=%s",
                    intento,
                    exc,
                )

        return None

    async def _detectar_y_actualizar_ciudad(
        self,
        flujo: Dict[str, Any],
        texto: str,
        cliente_id: Optional[str],
        perfil_cliente: Dict[str, Any],
        ubicacion: Optional[Dict[str, Any]] = None,
    ):
        """Detecta ciudad en el texto y la actualiza si es necesario."""
        ciudad_detectada = None
        _profesion_detectada, ciudad_detectada_texto = extraer_servicio_y_ubicacion(
            "", texto
        )
        if ciudad_detectada_texto:
            ciudad_detectada = ciudad_detectada_texto
        elif ubicacion:
            ciudad_detectada = extraer_ciudad_desde_payload_ubicacion(ubicacion)

        latitud = _parsear_coordenada((ubicacion or {}).get("latitude"))
        longitud = _parsear_coordenada((ubicacion or {}).get("longitude"))
        cliente_id_resuelto = flujo.get("customer_id") or cliente_id

        if (
            cliente_id_resuelto
            and latitud is not None
            and longitud is not None
            and self.repositorio_clientes
        ):
            perfil_con_ubicacion = await self.repositorio_clientes.actualizar_ubicacion(
                cliente_id_resuelto, latitud, longitud
            )
            if perfil_con_ubicacion:
                flujo["customer_id"] = perfil_con_ubicacion.get(
                    "id", cliente_id_resuelto
                )

        if not ciudad_detectada and latitud is not None and longitud is not None:
            ciudad_detectada = await self._resolver_ciudad_desde_coordenadas(
                latitud, longitud
            )
            if ciudad_detectada:
                self.logger.info(
                    "📍 geocode_city_resolved lat=%s lng=%s city=%s",
                    latitud,
                    longitud,
                    ciudad_detectada,
                )
            else:
                self.logger.info(
                    "⚠️ geocode_fallback_to_text lat=%s lng=%s",
                    latitud,
                    longitud,
                )

        if ciudad_detectada:
            ciudad_normalizada = ciudad_detectada
            ciudad_actual = (flujo.get("city") or "").strip()
            if ciudad_normalizada.lower() != ciudad_actual.lower():
                # Usar repositorio si está disponible, sino callback
                if self.repositorio_clientes:
                    perfil_actualizado = (
                        await self.repositorio_clientes.actualizar_ciudad(
                            flujo.get("customer_id") or cliente_id_resuelto,
                            ciudad_normalizada,
                        )
                    )
                else:
                    perfil_actualizado = await self.actualizar_ciudad_cliente(
                        flujo.get("customer_id") or cliente_id_resuelto,
                        ciudad_normalizada,
                    )
                if perfil_actualizado:
                    flujo["city"] = perfil_actualizado.get("city")
                    flujo["city_confirmed"] = True
                    flujo["city_confirmed_at"] = perfil_actualizado.get(
                        "city_confirmed_at"
                    )
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
            limpiar_ubicacion_cliente=getattr(self, "limpiar_ubicacion_cliente", None),
            limpiar_consentimiento_cliente=self.limpiar_consentimiento_cliente,
            mensaje_nueva_sesion_dict=mensaje_nueva_sesion_dict,
            reset_keywords=RESET_KEYWORDS,
            servicio_consentimiento=self.servicio_consentimiento,
            solicitar_consentimiento=self.solicitar_consentimiento,
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

    async def _disparar_prefetch_busqueda(
        self, telefono: str, flujo: Dict[str, Any]
    ) -> None:
        """Publica evento de prefetch al Redis Stream (fire-and-forget)."""
        from infrastructure.prefetch.publicador_prefetch import (
            publicar_prefetch_busqueda,
        )

        await publicar_prefetch_busqueda(telefono, flujo, self.redis_client)

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
        # NOTA: Ya no usamos catálogo estático de servicios.
        # IA detecta cualquier servicio.
        es_valido, mensaje_error = validar_entrada_servicio(
            texto or "",
            GREETINGS,
            {},  # Catálogo vacío - IA detecta servicios dinámicamente
        )

        if not es_valido:
            if (mensaje_error or "").strip() == mensaje_inicial_solicitud():
                return await responder(
                    flujo,
                    await self.construir_prompt_inicial_servicio(),
                )
            return await responder(
                flujo,
                {"response": mensaje_error},
            )

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
        funcion_validacion_necesidad = getattr(
            self.extractor_ia,
            "es_necesidad_o_problema",
            None,
        )

        flujo_actualizado, respuesta = await procesar_estado_esperando_servicio(
            flujo,
            texto,
            GREETINGS,
            mensaje_inicial_solicitud(),
            funcion_extraccion,
            funcion_validacion_necesidad,
            None,
            None,
            None,
            None,
            self.extractor_ia.generar_especializaciones_ocupacion,
        )
        flujo = flujo_actualizado

        # Si el manejador devuelve solo el prompt inicial sin UI, convertirlo a lista.
        if (
            flujo.get("state") == "awaiting_service"
            and isinstance(respuesta, dict)
            and not respuesta.get("ui")
            and (respuesta.get("response") or "").strip() == mensaje_inicial_solicitud()
        ):
            respuesta = await self.construir_prompt_inicial_servicio()

        if flujo.get("state") == "confirm_service":
            asyncio.create_task(self._disparar_prefetch_busqueda(telefono, flujo))
            return await responder(flujo, respuesta)

        servicio_confirmado = (flujo.get("service") or "").strip()
        if not servicio_confirmado:
            self.logger.info(
                "🔒 Flujo detenido en awaiting_service por falta de servicio: "
                "phone=%s state=%s",
                telefono,
                flujo.get("state"),
            )
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
        ubicacion: Optional[Dict[str, Any]],
        responder,
        guardar_mensaje_bot,
    ) -> Dict[str, Any]:
        """Procesa el estado 'awaiting_city'."""
        cliente_id = flujo.get("customer_id")
        # Usar repositorio si está disponible, sino callback
        if self.repositorio_clientes:
            await self.repositorio_clientes.obtener_o_crear(telefono=telefono)
        else:
            await self.obtener_o_crear_cliente(telefono)

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
                                "Por favor descríbelo nuevamente antes de "
                                "indicar la ciudad."
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
        ciudad_desde_ubicacion = extraer_ciudad_desde_payload_ubicacion(ubicacion)
        ciudad_entrada = ciudad_normalizada_entrada or ciudad_desde_ubicacion
        if (
            not ciudad_entrada
            and ubicacion
            and flujo.get("city_confirmed")
            and isinstance(flujo.get("city"), str)
            and flujo.get("city").strip()
        ):
            ciudad_entrada = flujo["city"].strip()

        if texto and not ciudad_entrada:
            return await responder(
                flujo,
                mensaje_error_ciudad_no_reconocida(),
            )

        from templates.mensajes.ubicacion import solicitar_ciudad_formato

        flujo_actualizado, respuesta = procesar_estado_esperando_ciudad(
            flujo,
            ciudad_entrada or texto,
            solicitar_ciudad_formato(),
        )

        if ciudad_entrada:
            entrada_normalizada = ciudad_entrada.strip().title()
            flujo_actualizado["city"] = entrada_normalizada
            flujo_actualizado["city_confirmed"] = True
            # Usar repositorio si está disponible, sino callback
            if self.repositorio_clientes:
                resultado_actualizacion = (
                    await self.repositorio_clientes.actualizar_ciudad(
                        flujo_actualizado.get("customer_id") or cliente_id,
                        entrada_normalizada,
                    )
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
                await self.construir_prompt_inicial_servicio(),
            )

        # Usar transicionar_a_busqueda_desde_ciudad
        ciudad_del_flujo = (
            flujo_actualizado.get("city")
            or (ciudad_entrada or texto).strip().title()
        )
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
                                "⚠️ La búsqueda tomó demasiado tiempo. "
                                "Por favor intenta nuevamente."
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
                "response": (
                    f"Estoy buscando {flujo.get('service')} "
                    f"en {flujo.get('city')}, espera un momento."
                )
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
