"""
Contratos (Interfaces) para el servicio AI Clientes.

Este módulo define Protocol classes que especifican las interfaces
que deben implementar los componentes del sistema. Usando typing.Protocol
permitimos duck typing con verificación de tipos estática.

Beneficios:
- Elimina la necesidad de inyección post-inicialización
- Permite testing con mocks fácilmente
- Documenta las dependencias explícitamente
- Facilita el intercambio de implementaciones
"""

from .repositorios import (
    IRepositorioFlujo,
    IRepositorioClientes,
)
from .servicios import (
    IBuscadorProveedores,
    IExtractorNecesidad,
    IModeradorContenido,
    IValidadorProveedores,
    IServicioConsentimiento,
)
from .eventos import (
    IProgramadorRetroalimentacion,
    IPublicadorEventos,
)

__all__ = [
    # Repositorios
    "IRepositorioFlujo",
    "IRepositorioClientes",
    # Servicios
    "IBuscadorProveedores",
    "IExtractorNecesidad",
    "IModeradorContenido",
    "IValidadorProveedores",
    "IServicioConsentimiento",
    # Eventos
    "IProgramadorRetroalimentacion",
    "IPublicadorEventos",
]
