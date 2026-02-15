"""
Contratos para servicios de eventos y mensajería.

Define las interfaces para publicación y procesamiento de eventos,
permitiendo diferentes implementaciones (Redis Streams, Supabase, etc.).
"""

from datetime import datetime
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class IProgramadorRetroalimentacion(Protocol):
    """
    Interfaz para el programador de retroalimentación.

    Implementaciones:
    - ProgramadorRetroalimentacion: Soporte dual Streams/Supabase
    """

    async def programar_solicitud_retroalimentacion(
        self,
        telefono: str,
        proveedor: Dict[str, Any],
        lead_event_id: str = "",
    ) -> None:
        """
        Programa una solicitud de retroalimentación diferida.

        Args:
            telefono: Teléfono del cliente
            proveedor: Datos del proveedor contactado
            lead_event_id: ID del evento de lead (opcional)
        """
        ...

    async def enviar_texto_whatsapp(self, telefono: str, texto: str) -> bool:
        """
        Envía un mensaje de WhatsApp.

        Args:
            telefono: Teléfono destinatario
            texto: Texto del mensaje

        Returns:
            True si el envío fue exitoso
        """
        ...

    def detener(self) -> None:
        """
        Detiene el programador de forma segura.
        """
        ...


@runtime_checkable
class IPublicadorEventos(Protocol):
    """
    Interfaz para publicación de eventos en un event bus.

    Implementaciones:
    - ProcesadorEventosRedisStreams: Publicación en Redis Streams
    """

    async def publicar_evento(
        self,
        tipo_evento: str,
        carga: Dict[str, Any],
        scheduled_at: Optional[datetime] = None,
    ) -> str:
        """
        Publica un evento en el bus.

        Args:
            tipo_evento: Tipo del evento (ej: "send_whatsapp")
            carga: Datos del evento
            scheduled_at: Fecha/hora programada (opcional)

        Returns:
            ID del evento publicado
        """
        ...


@runtime_checkable
class IProcesadorEventos(Protocol):
    """
    Interfaz para procesamiento de eventos desde un event bus.

    Implementaciones:
    - ProcesadorEventosRedisStreams: Procesamiento con consumer groups
    """

    async def bucle_procesamiento(self) -> None:
        """
        Inicia el bucle de procesamiento de eventos.
        Es bloqueante y se ejecuta indefinidamente hasta detener().
        """
        ...

    def detener(self) -> None:
        """
        Señaliza al procesador que debe detenerse.
        """
        ...

    async def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del procesador.

        Returns:
            Dict con métricas del stream y consumer group
        """
        ...
