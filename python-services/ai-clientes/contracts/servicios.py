"""
Contratos para servicios de dominio.

Define las interfaces que deben implementar los servicios
de lógica de negocio, permitiendo testing e intercambio
de implementaciones.
"""

from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class IBuscadorProveedores(Protocol):
    """
    Interfaz para el servicio de búsqueda de proveedores.

    Implementaciones:
    - BuscadorProveedores: Búsqueda con validación IA
    """

    async def buscar(
        self,
        profesion: str,
        ciudad: str,
        radio_km: float = 10.0,
        descripcion_problema: Optional[str] = None,
        limite: int = 10,
    ) -> Dict[str, Any]:
        """
        Busca proveedores que coincidan con los criterios.

        Args:
            profesion: Profesión o servicio buscado
            ciudad: Ciudad para filtrar
            radio_km: Radio de búsqueda en km
            descripcion_problema: Descripción del problema (opcional)
            limite: Máximo de resultados

        Returns:
            Dict con providers, total, y metadatos de búsqueda
        """
        ...


@runtime_checkable
class IExtractorNecesidad(Protocol):
    """
    Interfaz para el servicio de extracción de necesidades con IA.

    Implementaciones:
    - ExtractorNecesidadIA: Extracción con OpenAI GPT-4
    """

    async def extraer_servicio_con_ia_pura(
        self, texto_usuario: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extrae servicio y ciudad del texto del usuario usando IA.

        Args:
            texto_usuario: Texto del mensaje del usuario

        Returns:
            Tupla (servicio, ciudad) donde cualquiera puede ser None
        """
        ...

    async def extraer_necesidad(
        self, historial: str, mensaje_actual: str
    ) -> Dict[str, Any]:
        """
        Extrae la necesidad completa del usuario.

        Args:
            historial: Historial de la conversación
            mensaje_actual: Mensaje actual del usuario

        Returns:
            Dict con servicio, ciudad, confianza, etc.
        """
        ...


@runtime_checkable
class IModeradorContenido(Protocol):
    """
    Interfaz para el servicio de moderación de contenido.

    Implementaciones:
    - ModeradorContenido: Moderación con OpenAI y Redis
    """

    async def validar_contenido_con_ia(
        self, texto: str, telefono: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Valida el contenido del mensaje con IA.

        Args:
            texto: Texto a validar
            telefono: Teléfono del usuario (para tracking)

        Returns:
            Tupla (mensaje_advertencia, mensaje_ban) donde:
            - mensaje_advertencia: Advertencia si contenido inapropiado
            - mensaje_ban: Mensaje de ban si debe ser bloqueado
        """
        ...

    async def verificar_si_bloqueado(self, telefono: str) -> bool:
        """
        Verifica si un usuario está bloqueado.

        Args:
            telefono: Teléfono del usuario

        Returns:
            True si el usuario está bloqueado
        """
        ...


@runtime_checkable
class IValidadorProveedores(Protocol):
    """
    Interfaz para el servicio de validación de proveedores con IA.

    Implementaciones:
    - ValidadorProveedoresIA: Validación con OpenAI
    """

    async def validar_proveedor(
        self,
        profesion_buscada: str,
        profesion_proveedor: str,
        servicios: List[str],
        confianza_umbral: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Valida si un proveedor es relevante para la búsqueda.

        Args:
            profesion_buscada: Profesión buscada por el usuario
            profesion_proveedor: Profesión del proveedor
            servicios: Lista de servicios del proveedor
            confianza_umbral: Umbral de confianza mínimo

        Returns:
            Dict con es_valido, confianza, razon
        """
        ...


@runtime_checkable
class IServicioConsentimiento(Protocol):
    """
    Interfaz para el servicio de gestión de consentimiento GDPR.

    Implementaciones:
    - ServicioConsentimiento: Gestión con Supabase
    """

    async def verificar_consentimiento(
        self, telefono: str
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Verifica si el usuario ha dado consentimiento.

        Args:
            telefono: Teléfono del usuario

        Returns:
            Tupla (tiene_consentimiento, perfil_cliente)
        """
        ...

    async def registrar_consentimiento(
        self, cliente_id: str, acepta: bool
    ) -> bool:
        """
        Registra la respuesta de consentimiento.

        Args:
            cliente_id: ID del cliente
            acepta: True si acepta, False si no

        Returns:
            True si el registro fue exitoso
        """
        ...
