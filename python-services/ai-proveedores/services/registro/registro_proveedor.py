"""
Funciones de registro de proveedores en base de datos.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from models.proveedores import SolicitudCreacionProveedor
from supabase import Client

from services.registro.normalizacion import normalizar_datos_proveedor, garantizar_campos_obligatorios_proveedor
from infrastructure.database import run_supabase

logger = logging.getLogger(__name__)


async def registrar_proveedor_en_base_datos(
    supabase: Client,
    datos_proveedor: SolicitudCreacionProveedor,
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Registra proveedor usando el esquema unificado simplificado.

    Esta función realiza las siguientes operaciones:
    1. Normaliza los datos del proveedor
    2. Ejecuta un upsert en la tabla providers (conflicto en campo phone)
    3. Recupera el registro insertado/actualizado
    4. Aplica valores por defecto a campos obligatorios
    5. Actualiza el caché de búsqueda

    Args:
        supabase: Cliente de Supabase
        datos_proveedor: Datos del proveedor a registrar
        timeout: Timeout para operaciones de Supabase (segundos)

    Returns:
        Dict con el proveedor registrado o None si falló
    """
    if not supabase:
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

            perfil_normalizado = garantizar_campos_obligatorios_proveedor(provider_record)
            # Importar localmente para evitar ciclo de importación
            from services.search_cache import cachear_perfil_proveedor

            await cachear_perfil_proveedor(
                perfil_normalizado.get("phone", datos_normalizados["phone"]),
                perfil_normalizado,
            )
            return perfil_normalizado
        else:
            logger.error("❌ No se pudo registrar proveedor")
            return None

    except Exception as e:
        logger.error(f"❌ Error en registrar_proveedor_en_base_datos: {e}")
        return None
