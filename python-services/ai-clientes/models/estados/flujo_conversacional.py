"""
Schema validado para el flujo conversacional usando Pydantic.

Este módulo define el modelo principal FlujoConversacional que reemplaza
el uso de dicts sin validación en el repositorio de flujo.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _utcnow() -> str:
    """Retorna timestamp ISO UTC actual."""
    return datetime.now(timezone.utc).isoformat()


class EstadoConversacion(str, Enum):
    """
    Estados válidos de la máquina de estados conversacional.

    Flujo principal:
    awaiting_consent -> awaiting_service -> confirm_service ->
    awaiting_city -> searching -> presenting_results ->
    viewing_provider_detail -> confirm_new_search -> ...
    """

    # Consentimiento inicial (GDPR)
    AWAITING_CONSENT = "awaiting_consent"

    # Solicitar servicio
    AWAITING_SERVICE = "awaiting_service"
    CONFIRM_SERVICE = "confirm_service"

    # Solicitar ubicación
    AWAITING_CITY = "awaiting_city"

    # Búsqueda en progreso
    SEARCHING = "searching"

    # Presentar resultados
    PRESENTING_RESULTS = "presenting_results"

    # Ver detalle de proveedor
    VIEWING_PROVIDER_DETAIL = "viewing_provider_detail"

    # Confirmar nueva búsqueda
    CONFIRM_NEW_SEARCH = "confirm_new_search"

    # Esperar confirmación de ciudad
    AWAITING_CITY_CONFIRMATION = "awaiting_city_confirmation"

    # Flujo de retroalimentación
    AWAITING_HIRING_FEEDBACK = "awaiting_hiring_feedback"

    # Estado para compartir contacto
    AWAITING_CONTACT_SHARE = "awaiting_contact_share"

    # Estados especiales
    COMPLETED = "completed"
    ERROR = "error"


class ProveedorSeleccionado(BaseModel):
    """Modelo para un proveedor en la lista de resultados."""

    id: str
    phone_number: Optional[str] = None
    real_phone: Optional[str] = None
    full_name: Optional[str] = None
    name: Optional[str] = None
    city: Optional[str] = None
    rating: float = Field(default=0.0, ge=0.0, le=5.0)
    available: bool = True
    verified: bool = False
    professions: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    years_of_experience: Optional[int] = None
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    face_photo_url: Optional[str] = None
    social_media_url: Optional[str] = None
    social_media_type: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"extra": "allow"}  # Permitir campos adicionales


class ContextoBusqueda(BaseModel):
    """Contexto de la búsqueda actual."""

    servicio: str
    ciudad: Optional[str] = None
    descripcion_problema: Optional[str] = None
    radio_km: float = Field(default=10.0, ge=0.1, le=100.0)
    limite: int = Field(default=10, ge=1, le=50)
    timestamp_inicio: Optional[str] = None
    estrategia_usada: Optional[str] = None
    tiempo_ms: Optional[float] = None


class FlujoConversacional(BaseModel):
    """
    Modelo principal del flujo conversacional.

    Este schema reemplaza el uso de dicts sin validación y garantiza
    que todos los estados persistidos en Redis tengan una estructura válida.
    """

    # Identificador del usuario
    telefono: str = Field(..., min_length=1, max_length=20)

    # Estado actual de la conversación
    state: EstadoConversacion = Field(default=EstadoConversacion.AWAITING_SERVICE)

    # Servicio solicitado
    service: Optional[str] = Field(default=None, max_length=500)
    service_full: Optional[str] = Field(default=None, max_length=1000)

    # Ubicación
    city: Optional[str] = Field(default=None, max_length=100)
    city_confirmed: bool = False
    city_confirmed_at: Optional[str] = None

    # Resultados de búsqueda
    providers: List[Dict[str, Any]] = Field(default_factory=list)
    provider_detail_idx: Optional[int] = Field(default=None, ge=0)

    # Proveedor seleccionado
    chosen_provider: Optional[Dict[str, Any]] = None

    # Contexto de búsqueda
    searching_dispatched: bool = False
    searching_started_at: Optional[str] = None

    # Cliente
    customer_id: Optional[str] = None
    has_consent: bool = False

    # Retroalimentación
    pending_feedback_lead_event_id: Optional[str] = None
    pending_feedback_provider_name: Optional[str] = None

    # Confirmación de nueva búsqueda
    confirm_title: Optional[str] = None
    confirm_include_city_option: bool = False
    confirm_attempts: int = Field(default=0, ge=0, le=10)

    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_message_at: Optional[str] = None

    model_config = {"extra": "allow"}  # Permitir campos adicionales para backward compatibility

    @field_validator("telefono")
    @classmethod
    def validar_telefono(cls, v: str) -> str:
        """Normaliza el formato del teléfono."""
        # Remover espacios y caracteres no numéricos excepto +
        telefono_limpio = "".join(c for c in v if c.isdigit() or c == "+")
        if not telefono_limpio:
            raise ValueError("Teléfono no puede estar vacío")
        return telefono_limpio

    @model_validator(mode="after")
    def validar_consistencia(self) -> "FlujoConversacional":
        """Valida la consistencia entre estado y datos."""
        # Si está buscando, debe tener servicio y ciudad
        if self.state == EstadoConversacion.SEARCHING:
            if not self.service:
                raise ValueError("Estado SEARCHING requiere servicio definido")

        # Si está presentando resultados, debe tener proveedores
        if self.state == EstadoConversacion.PRESENTING_RESULTS:
            if not self.providers:
                # Permitir lista vacía pero advertir
                pass

        # Si está viendo detalle, debe tener índice válido
        if self.state == EstadoConversacion.VIEWING_PROVIDER_DETAIL:
            if self.provider_detail_idx is not None and self.providers:
                if self.provider_detail_idx >= len(self.providers):
                    raise ValueError("Índice de proveedor fuera de rango")

        return self

    def puede_transicionar_a(self, nuevo_estado: EstadoConversacion) -> bool:
        """
        Verifica si la transición al nuevo estado es válida.

        Args:
            nuevo_estado: Estado destino de la transición

        Returns:
            True si la transición es válida, False en caso contrario
        """
        from .transiciones import puede_transicionar
        return puede_transicionar(self.state, nuevo_estado)

    def transicionar_a(self, nuevo_estado: EstadoConversacion) -> "FlujoConversacional":
        """
        Realiza una transición de estado validada.

        Args:
            nuevo_estado: Estado destino de la transición

        Returns:
            Nueva instancia con el estado actualizado

        Raises:
            ValueError: Si la transición no es válida
        """
        if not self.puede_transicionar_a(nuevo_estado):
            from .transiciones import obtener_transiciones_validas
            validas = obtener_transiciones_validas(self.state)
            raise ValueError(
                f"Transición inválida de {self.state.value} a {nuevo_estado.value}. "
                f"Estados válidos: {[s.value for s in validas]}"
            )

        # Crear nueva instancia con el estado actualizado
        datos = self.model_dump()
        datos["state"] = nuevo_estado
        datos["updated_at"] = _utcnow()

        return FlujoConversacional(**datos)

    def actualizar(
        self,
        **kwargs,
    ) -> "FlujoConversacional":
        """
        Actualiza campos del flujo de forma inmutable.

        Returns:
            Nueva instancia con los campos actualizados
        """
        datos = self.model_dump()
        datos.update(kwargs)
        datos["updated_at"] = _utcnow()

        return FlujoConversacional(**datos)

    def agregar_proveedores(
        self, proveedores: List[Dict[str, Any]]
    ) -> "FlujoConversacional":
        """
        Agrega proveedores a la lista de resultados.

        Args:
            proveedores: Lista de proveedores encontrados

        Returns:
            Nueva instancia con los proveedores agregados
        """
        datos = self.model_dump()
        datos["providers"] = proveedores
        datos["searching_dispatched"] = False
        datos.pop("searching_started_at", None)
        datos["updated_at"] = _utcnow()

        return FlujoConversacional(**datos)

    def seleccionar_proveedor(self, indice: int) -> "FlujoConversacional":
        """
        Selecciona un proveedor de la lista por índice.

        Args:
            indice: Índice del proveedor en la lista

        Returns:
            Nueva instancia con el proveedor seleccionado

        Raises:
            ValueError: Si el índice está fuera de rango
        """
        if not self.providers:
            raise ValueError("No hay proveedores para seleccionar")
        if indice < 0 or indice >= len(self.providers):
            raise ValueError(f"Índice {indice} fuera de rango (0-{len(self.providers)-1})")

        datos = self.model_dump()
        datos["provider_detail_idx"] = indice
        datos["chosen_provider"] = self.providers[indice]
        datos["updated_at"] = _utcnow()

        return FlujoConversacional(**datos)

    def resetear(self) -> "FlujoConversacional":
        """
        Resetea el flujo a su estado inicial.

        Returns:
            Nueva instancia con estado inicial
        """
        return FlujoConversacional(
            telefono=self.telefono,
            state=EstadoConversacion.AWAITING_SERVICE,
            customer_id=self.customer_id,
            has_consent=self.has_consent,
            city=self.city,
            city_confirmed=self.city_confirmed,
            city_confirmed_at=self.city_confirmed_at,
            created_at=self.created_at,
            updated_at=_utcnow(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el modelo a diccionario para persistencia.

        Returns:
            Dict con los datos del flujo
        """
        return self.model_dump()

    @classmethod
    def from_dict(cls, datos: Dict[str, Any]) -> "FlujoConversacional":
        """
        Crea una instancia desde un diccionario.

        Maneja backward compatibility con datos legacy que pueden
        no tener todos los campos o tener estados obsoletos.

        Args:
            datos: Diccionario con datos del flujo

        Returns:
            Instancia de FlujoConversacional
        """
        # Normalizar estado legacy
        estado_raw = datos.get("state", "awaiting_service")
        try:
            estado = EstadoConversacion(estado_raw)
        except ValueError:
            # Estado legacy o inválido, usar default
            estado = EstadoConversacion.AWAITING_SERVICE

        # Crear copia para no mutar el original
        datos_normalizados = dict(datos)
        datos_normalizados["state"] = estado

        # Asegurar que teléfono existe
        if "telefono" not in datos_normalizados:
            # Intentar obtener de otras fuentes
            telefono = datos_normalizados.get("phone") or datos_normalizados.get("from") or "unknown"
            datos_normalizados["telefono"] = telefono

        return cls(**datos_normalizados)
