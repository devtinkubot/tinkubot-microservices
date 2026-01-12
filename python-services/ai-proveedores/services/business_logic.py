"""
Lógica de negocio para registro y gestión de proveedores.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from models.schemas import ProviderCreate
from supabase import Client

from utils.services_utils import formatear_servicios, normalizar_profesion_para_storage, normalizar_texto_para_busqueda, sanitizar_servicios
from utils.db_utils import run_supabase

logger = logging.getLogger(__name__)


def normalizar_datos_proveedor(datos_crudos: ProviderCreate) -> Dict[str, Any]:
    """
    Normaliza datos del formulario para el esquema unificado.
    """
    servicios_limpios = sanitizar_servicios(datos_crudos.services_list or [])

    datos = {
        "phone": datos_crudos.phone.strip(),
        "full_name": datos_crudos.full_name.strip().title(),  # Formato legible
        "email": datos_crudos.email.strip() if datos_crudos.email else None,
        "city": normalizar_texto_para_busqueda(datos_crudos.city),  # minúsculas
        "profession": normalizar_profesion_para_storage(
            datos_crudos.profession
        ),  # minúsculas y abreviaturas expandidas
        "services": formatear_servicios(servicios_limpios),
        "experience_years": datos_crudos.experience_years or 0,
        "has_consent": datos_crudos.has_consent,
        "verified": False,
        # Arrancamos en 5 para promediar con futuras calificaciones de clientes.
        "rating": 5.0,
        "social_media_url": datos_crudos.social_media_url,
        "social_media_type": datos_crudos.social_media_type,
    }

    # Agregar real_phone y phone_verified si están disponibles
    if hasattr(datos_crudos, 'real_phone') and datos_crudos.real_phone:
        datos["real_phone"] = datos_crudos.real_phone.strip()
    if hasattr(datos_crudos, 'phone_verified') and datos_crudos.phone_verified is not None:
        datos["phone_verified"] = datos_crudos.phone_verified

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
    datos_proveedor: ProviderCreate,
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Registra proveedor usando el esquema unificado simplificado.

    Args:
        supabase: Cliente de Supabase
        datos_proveedor: Datos del proveedor a registrar
        timeout: Timeout para operaciones de Supabase (segundos)

    Returns:
        Dict con el proveedor registrado o None si falló
    """
    if not supabase:
        logger.warning("⚠️ Supabase client no disponible para registrar proveedor")
        return None

    try:
        # Normalizar datos
        datos_normalizados = normalizar_datos_proveedor(datos_proveedor)

        # Upsert por teléfono: reabre rechazados como pending, evita doble round-trip
        upsert_payload = {
            **datos_normalizados,
            "verified": False,
            "updated_at": datetime.utcnow().isoformat(),
        }

        resultado = await run_supabase(
            lambda: supabase.table("providers")
            .upsert(upsert_payload, on_conflict="phone")
            .execute(),
            timeout=timeout,
            label="providers.upsert",
        )
        error_respuesta = getattr(resultado, "error", None)
        if error_respuesta:
            logger.error("❌ Supabase rechazó el registro/upsert: %s", error_respuesta)
            return None

        registro_insertado: Optional[Dict[str, Any]] = None
        data_resultado = getattr(resultado, "data", None)
        if isinstance(data_resultado, list) and data_resultado:
            registro_insertado = data_resultado[0]
        elif isinstance(data_resultado, dict) and data_resultado:
            registro_insertado = data_resultado

        # Algunos proyectos usan Prefer: return=minimal, hacer fetch adicional
        if registro_insertado is None:
            try:
                refetch = await run_supabase(
                    lambda: supabase.table("providers")
                    .select("*")
                    .eq("phone", datos_normalizados["phone"])
                    .limit(1)
                    .execute(),
                    timeout=timeout,
                    label="providers.fetch_after_upsert",
                )
                if refetch.data:
                    registro_insertado = refetch.data[0]
            except Exception as refetch_error:
                logger.warning(
                    "⚠️ No se pudo recuperar proveedor recién creado: %s",
                    refetch_error,
                )

        if registro_insertado:
            id_proveedor = registro_insertado.get("id")
            logger.info(f"✅ Proveedor registrado en esquema unificado: {id_proveedor}")

            provider_record = {
                "id": id_proveedor,
                "phone": registro_insertado.get("phone", datos_normalizados["phone"]),
                "full_name": registro_insertado.get(
                    "full_name", datos_normalizados["full_name"]
                ),
                "email": registro_insertado.get("email", datos_normalizados["email"]),
                "city": registro_insertado.get("city", datos_normalizados["city"]),
                "profession": registro_insertado.get(
                    "profession", datos_normalizados["profession"]
                ),
                "services": registro_insertado.get(
                    "services", datos_normalizados["services"]
                ),
                "experience_years": registro_insertado.get(
                    "experience_years", datos_normalizados["experience_years"]
                ),
                "rating": registro_insertado.get("rating", datos_normalizados["rating"]),
                "verified": registro_insertado.get(
                    "verified", datos_normalizados["verified"]
                ),
                "has_consent": registro_insertado.get(
                    "has_consent", datos_normalizados["has_consent"]
                ),
                "social_media_url": registro_insertado.get(
                    "social_media_url", datos_normalizados["social_media_url"]
                ),
                "social_media_type": registro_insertado.get(
                    "social_media_type", datos_normalizados["social_media_type"]
                ),
                "created_at": registro_insertado.get(
                    "created_at", datetime.now().isoformat()
                ),
            }

            # Agregar real_phone y phone_verified si están en los datos
            if "real_phone" in datos_normalizados:
                provider_record["real_phone"] = registro_insertado.get(
                    "real_phone", datos_normalizados.get("real_phone")
                )
            if "phone_verified" in datos_normalizados:
                provider_record["phone_verified"] = registro_insertado.get(
                    "phone_verified", datos_normalizados.get("phone_verified")
                )

            perfil_normalizado = aplicar_valores_por_defecto_proveedor(provider_record)
            # Importar localmente para evitar ciclo de importación
            # CORRECCIÓN: search_cache no existe, usar profile_service
            from services.profile_service import cachear_perfil_proveedor

            await cachear_perfil_proveedor(
                perfil_normalizado.get("phone", datos_normalizados["phone"]),
                perfil_normalizado,
            )
            return perfil_normalizado
        else:
            logger.error("❌ No se pudo registrar proveedor")
            return None

    except Exception as e:
        logger.error(f"❌ Error en registrar_proveedor: {e}")
        return None
