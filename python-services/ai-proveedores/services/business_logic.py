"""
Lógica de negocio para registro y gestión de proveedores.

Feature Flags:
- USE_REPOSITORY_PATTERN: Habilita el nuevo Repository Pattern para acceso a datos
  False: Usa implementación original (actual)
  True: Usa Repository Pattern con Command/Saga
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from supabase import Client

from utils.services_utils import formatear_servicios, normalizar_profesion_para_storage, normalizar_texto_para_busqueda, sanitizar_servicios
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)

# Feature Flag: Repository Pattern (Fase 1.1)
# ACTIVADO: Repository Pattern habilitado para producción
USE_REPOSITORY_PATTERN = True


def normalizar_datos_proveedor(datos_crudos: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza datos del formulario para el esquema unificado.

    Principio Single Responsibility (SRP):
    - Esta función solo normaliza datos
    - No valida ni transforma estructuras complejas
    - Trabaja con dicts para máxima flexibilidad

    Args:
        datos_crudos: Dict con los datos del proveedor (puede venir de Pydantic o directo)

    Returns:
        Dict con los datos normalizados para Supabase
    """
    # Extraer services_list de forma segura (compatible con dict y Pydantic models)
    services_list = []
    if isinstance(datos_crudos, dict):
        # Viene de validate_provider_payload.model_dump()
        services_list = datos_crudos.get("services_list") or []
    else:
        # Viene como objeto Pydantic
        services_list = getattr(datos_crudos, 'services_list', []) or []

    servicios_limpios = sanitizar_servicios(services_list)

    # Extraer campos con fallback seguro para dict y objetos
    def get_field(field: str, default=None):
        if isinstance(datos_crudos, dict):
            return datos_crudos.get(field, default)
        return getattr(datos_crudos, field, default)

    phone = get_field("phone", "")
    full_name = get_field("full_name", "")
    email = get_field("email")
    city = get_field("city", "")
    profession = get_field("profession", "")
    experience_years = get_field("experience_years", 0)
    has_consent = get_field("has_consent", False)
    social_media_url = get_field("social_media_url")
    social_media_type = get_field("social_media_type")
    real_phone = get_field("real_phone")
    phone_verified = get_field("phone_verified")

    datos = {
        "phone": phone.strip() if phone else "",
        "full_name": full_name.strip().title() if full_name else "",  # Formato legible
        "email": email.strip() if email else None,
        "city": normalizar_texto_para_busqueda(city) if city else "",  # minúsculas
        "profession": normalizar_profesion_para_storage(
            profession
        ) if profession else "",  # minúsculas y abreviaturas expandidas
        "services": formatear_servicios(servicios_limpios),
        "experience_years": experience_years or 0,
        "has_consent": bool(has_consent),
        "verified": False,
        # Arrancamos en 5 para promediar con futuras calificaciones de clientes.
        "rating": 5.0,
        "social_media_url": social_media_url,
        "social_media_type": social_media_type,
    }

    # Agregar real_phone y phone_verified si están disponibles
    if real_phone:
        datos["real_phone"] = real_phone.strip()
    if phone_verified is not None:
        datos["phone_verified"] = phone_verified

    return datos


def aplicar_valores_por_defecto_proveedor(
    registro: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Garantiza que los campos obligatorios existan aunque la tabla no los tenga.
    """
    datos = dict(registro or {})
    datos.setdefault("verified", False)

    available_value = datos.get("available")
    if available_value is None:
        available_value = datos.get("verified", True)
    datos["available"] = bool(available_value)

    datos["rating"] = float(datos.get("rating") or 5.0)
    datos["experience_years"] = int(datos.get("experience_years") or 0)
    datos["services"] = datos.get("services") or ""
    datos["has_consent"] = bool(datos.get("has_consent"))
    datos["status"] = "approved" if datos.get("verified") else "pending"
    return datos


async def registrar_proveedor(
    supabase: Client,
    datos_proveedor: Dict[str, Any],
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Registra proveedor usando Repository Pattern con Command/Saga.

    Principio Dependency Inversion (DIP):
    - Acepta Dict en lugar de ProviderCreate específico
    - Permite flexibilidad en el origen de los datos
    - La validación ocurre antes de llamar esta función

    Esta implementación usa:
    - SupabaseProviderRepository para acceso a datos
    - RegisterProviderCommand para encapsular la operación
    - ProviderRegistrationSaga para rollback automático

    Args:
        supabase: Cliente de Supabase
        datos_proveedor: Dict con los datos del proveedor a registrar
        timeout: Timeout para operaciones (no usado en Repository, el timeout es interno)

    Returns:
        Dict con el proveedor registrado o None si falló
    """
    if not supabase:
        logger.warning("⚠️ Supabase client no disponible para registrar proveedor")
        return None

    return await _registrar_proveedor_with_repository(supabase, datos_proveedor, timeout)


async def _registrar_proveedor_with_repository(
    supabase: Client,
    datos_proveedor: Dict[str, Any],
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Implementación principal de registro usando Repository Pattern.

    Esta implementación usa:
    - SupabaseProviderRepository para acceso a datos
    - RegisterProviderCommand para encapsular la operación
    - ProviderRegistrationSaga para rollback automático

    Args:
        supabase: Cliente de Supabase
        datos_proveedor: Dict con los datos del proveedor a registrar
        timeout: Timeout para operaciones (no usado en Repository, el timeout es interno)

    Returns:
        Dict con el proveedor registrado o None si falló
    """
    try:
        from repositories.provider_repository import SupabaseProviderRepository
        from core.commands import RegisterProviderCommand
        from core.saga import ProviderRegistrationSaga

        logger.info("🔧 Usando Repository Pattern para registro")

        # Crear repositorio
        repo = SupabaseProviderRepository(supabase)

        # Crear saga con el comando de registro
        saga = ProviderRegistrationSaga()
        saga.add_command(RegisterProviderCommand(repo, datos_proveedor))

        # Ejecutar saga (con rollback automático si falla)
        result = await saga.execute()

        # Buscar el proveedor registrado para mantener compatibilidad con el código existente
        phone = datos_proveedor.get("phone", "")
        if phone:
            provider = await repo.find_by_phone(phone)
            if provider:
                logger.info(f"✅ Proveedor registrado con Repository Pattern: {provider.get('id')}")

                # Cachear perfil para mantener compatibilidad
                from services.profile_service import cachear_perfil_proveedor
                perfil_normalizado = aplicar_valores_por_defecto_proveedor(provider)
                await cachear_perfil_proveedor(phone, perfil_normalizado)

                return perfil_normalizado

        logger.warning("⚠️ Repository Pattern ejecutó pero no se encontró el proveedor")
        return None

    except Exception as e:
        logger.error(f"❌ Error en Repository Pattern: {e}")
        return None
