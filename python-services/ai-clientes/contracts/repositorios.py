"""
Contratos para repositorios de persistencia.

Define las interfaces que deben implementar los repositorios
para acceso a datos, permitiendo intercambiar implementaciones
(Redis, Supabase, etc.) sin afectar la lógica de negocio.
"""

from typing import Any, Dict, Optional, Protocol, runtime_checkable

from models.estados import EstadoConversacion, FlujoConversacional


@runtime_checkable
class IRepositorioFlujo(Protocol):
    """
    Interfaz para el repositorio de flujos conversacionales.

    Implementaciones:
    - RepositorioFlujoRedis: Persistencia en Redis con TTL
    """

    async def obtener(self, telefono: str) -> Dict[str, Any]:
        """
        Obtiene el flujo de conversación de un teléfono.

        Args:
            telefono: Número de teléfono del usuario

        Returns:
            Dict con los datos del flujo (validado con Pydantic)
        """
        ...

    async def obtener_modelo(self, telefono: str) -> FlujoConversacional:
        """
        Obtiene el flujo como modelo Pydantic validado.

        Args:
            telefono: Número de teléfono del usuario

        Returns:
            Instancia de FlujoConversacional
        """
        ...

    async def guardar(self, telefono: str, datos: Dict[str, Any]) -> None:
        """
        Guarda el flujo de conversación.

        Args:
            telefono: Número de teléfono del usuario
            datos: Datos del flujo a guardar
        """
        ...

    async def guardar_modelo(self, flujo: FlujoConversacional) -> None:
        """
        Guarda un modelo FlujoConversacional directamente.

        Args:
            flujo: Instancia de FlujoConversacional a guardar
        """
        ...

    async def resetear(self, telefono: str) -> None:
        """
        Elimina el flujo de conversación.

        Args:
            telefono: Número de teléfono del usuario
        """
        ...

    async def actualizar_campo(
        self, telefono: str, campo: str, valor: Any
    ) -> Dict[str, Any]:
        """
        Actualiza un campo específico del flujo.

        Args:
            telefono: Número de teléfono del usuario
            campo: Nombre del campo a actualizar
            valor: Nuevo valor del campo

        Returns:
            Dict con el flujo actualizado
        """
        ...

    async def eliminar_campo(self, telefono: str, campo: str) -> Dict[str, Any]:
        """
        Elimina un campo específico del flujo.

        Args:
            telefono: Número de teléfono del usuario
            campo: Nombre del campo a eliminar

        Returns:
            Dict con el flujo actualizado
        """
        ...

    async def transicionar_estado(
        self, telefono: str, nuevo_estado: EstadoConversacion
    ) -> Optional[FlujoConversacional]:
        """
        Realiza una transición de estado validada.

        Args:
            telefono: Número de teléfono del usuario
            nuevo_estado: Estado destino

        Returns:
            FlujoConversacional actualizado o None si la transición es inválida
        """
        ...


@runtime_checkable
class IRepositorioClientes(Protocol):
    """
    Interfaz para el repositorio de clientes.

    Implementaciones:
    - RepositorioClientesSupabase: Persistencia en Supabase
    """

    async def obtener_o_crear(
        self,
        telefono: str,
        *,
        nombre_completo: Optional[str] = None,
        ciudad: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Obtiene o crea un cliente por teléfono.

        Args:
            telefono: Número de teléfono del cliente
            nombre_completo: Nombre completo opcional del cliente
            ciudad: Ciudad opcional del cliente

        Returns:
            Dict con los datos del cliente o None
        """
        ...

    async def actualizar_ciudad(
        self, cliente_id: str, ciudad: str
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza la ciudad del cliente.

        Args:
            cliente_id: ID del cliente
            ciudad: Nueva ciudad

        Returns:
            Dict con los datos actualizados o None si falla
        """
        ...

    async def actualizar_consentimiento(
        self, cliente_id: str, tiene_consentimiento: bool
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza el consentimiento GDPR del cliente.

        Args:
            cliente_id: ID del cliente
            tiene_consentimiento: True si acepta, False si no

        Returns:
            Dict con datos actualizados o None
        """
        ...

    async def limpiar_ciudad(self, cliente_id: Optional[str]) -> None:
        """
        Limpia la ciudad del cliente.

        Args:
            cliente_id: ID del cliente

        Returns:
            None
        """
        ...

    async def limpiar_consentimiento(self, cliente_id: Optional[str]) -> None:
        """
        Limpia el consentimiento del cliente.

        Args:
            cliente_id: ID del cliente

        Returns:
            None
        """
        ...

    async def registrar_consentimiento(
        self,
        usuario_id: str,
        respuesta: str,
        datos_consentimiento: Dict[str, Any],
    ) -> bool:
        """
        Registra evidencia legal de consentimiento.

        Args:
            usuario_id: ID del usuario
            respuesta: "accepted" o "declined"
            datos_consentimiento: Metadata del consentimiento

        Returns:
            True si el registro fue exitoso, False en caso contrario
        """
        ...
