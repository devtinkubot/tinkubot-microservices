"""Paquete services con exports perezosos para evitar imports colaterales."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "normalizar_datos_proveedor": ("services.onboarding.registration", "normalizar_datos_proveedor"),
    "garantizar_campos_obligatorios_proveedor": (
        "services.onboarding.registration",
        "garantizar_campos_obligatorios_proveedor",
    ),
    "insertar_servicios_proveedor": (
        "services.onboarding.registration",
        "insertar_servicios_proveedor",
    ),
    "registrar_proveedor_en_base_datos": (
        "services.onboarding.registration",
        "registrar_proveedor_en_base_datos",
    ),
    "asegurar_proveedor_borrador": (
        "services.onboarding.registration",
        "asegurar_proveedor_borrador",
    ),
    "limpiar_onboarding_proveedores": (
        "services.onboarding.registration",
        "limpiar_onboarding_proveedores",
    ),
    "validar_y_construir_proveedor": (
        "services.onboarding.registration",
        "validar_y_construir_proveedor",
    ),
    "eliminar_registro_proveedor": ("services.onboarding.registration", "eliminar_registro_proveedor"),
    "actualizar_perfil_profesional": (
        "services.maintenance",
        "actualizar_perfil_profesional",
    ),
    "actualizar_servicios": ("services.maintenance", "actualizar_servicios"),
    "agregar_servicios_proveedor": (
        "services.maintenance",
        "agregar_servicios_proveedor",
    ),
    "eliminar_servicio_proveedor": (
        "services.maintenance",
        "eliminar_servicio_proveedor",
    ),
    "actualizar_redes_sociales": (
        "services.maintenance",
        "actualizar_redes_sociales",
    ),
    "actualizar_selfie": ("services.maintenance", "actualizar_selfie"),
    "actualizar_nombre_proveedor": (
        "services.maintenance",
        "actualizar_nombre_proveedor",
    ),
    "actualizar_documentos_identidad": (
        "services.maintenance",
        "actualizar_documentos_identidad",
    ),
    "agregar_certificado_proveedor": (
        "services.maintenance",
        "agregar_certificado_proveedor",
    ),
    "actualizar_certificado_proveedor": (
        "services.maintenance",
        "actualizar_certificado_proveedor",
    ),
    "listar_certificados_proveedor": (
        "services.maintenance",
        "listar_certificados_proveedor",
    ),
    "eliminar_certificado_proveedor": (
        "services.maintenance",
        "eliminar_certificado_proveedor",
    ),
    "perfil_profesional_completo": (
        "services.maintenance",
        "perfil_profesional_completo",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module 'services' has no attribute {name!r}")

    modulo_nombre, atributo = _EXPORTS[name]
    modulo = import_module(modulo_nombre)
    valor = getattr(modulo, atributo)
    globals()[name] = valor
    return valor
