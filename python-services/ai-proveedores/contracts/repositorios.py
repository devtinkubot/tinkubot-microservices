from __future__ import annotations

from typing import Any, List, Protocol, runtime_checkable


@runtime_checkable
class IRepositorioServiciosProveedor(Protocol):
    """Contrato para persistencia de servicios de un proveedor."""

    async def obtener_servicios(self, proveedor_id: str) -> List[str]: ...

    async def actualizar_servicios(
        self, proveedor_id: str, servicios: List[Any]
    ) -> List[str]: ...

    async def agregar_servicios(
        self, proveedor_id: str, nuevos_servicios: List[Any]
    ) -> List[str]: ...

    async def eliminar_servicio(
        self, proveedor_id: str, indice_servicio: int
    ) -> List[str]: ...
