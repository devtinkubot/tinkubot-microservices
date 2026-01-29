"""
Funciones de registro de proveedores en base de datos.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from models.proveedores import SolicitudCreacionProveedor
from supabase import Client

from services.registro.normalizacion import normalizar_datos_proveedor, garantizar_campos_obligatorios_proveedor
from infrastructure.database import run_supabase

# Fase 6: Importar servicio de embeddings
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from services.servicios_proveedor.utilidades import normalizar_texto_para_busqueda

logger = logging.getLogger(__name__)


async def insertar_servicios_proveedor(
    supabase: Client,
    provider_id: str,
    servicios: List[str],
    embeddings_service: Optional[ServicioEmbeddings],
    timeout: float = 5.0,
) -> List[Dict[str, Any]]:
    """
    Inserta servicios individuales en provider_services con embeddings.

    Fase 6: Nueva función para gestionar la inserción de servicios con embeddings
    en la tabla provider_services. Cada servicio se inserta individualmente con
    su propio embedding vectorial para búsquedas semánticas.

    Args:
        supabase: Cliente de Supabase
        provider_id: ID del proveedor
        servicios: Lista de servicios normalizados
        embeddings_service: Servicio para generar embeddings (opcional)
        timeout: Timeout para operaciones de Supabase (segundos)

    Returns:
        Lista de servicios insertados con sus IDs y embeddings

    Example:
        >>> servicios = ["Plomería", "Electricidad", "Gasfitería"]
        >>> insertados = await insertar_servicios_proveedor(
        ...     supabase, "prov-123", servicios, embeddings_service
        ... )
        >>> print(len(insertados))  # 3
    """
    servicios_insertados = []

    if not embeddings_service:
        logger.warning("⚠️ Servicio de embeddings no disponible, no se generarán embeddings")
        # Si no hay servicio de embeddings, igual insertamos los servicios sin embedding
        for idx, servicio in enumerate(servicios):
            servicio_normalizado = normalizar_texto_para_busqueda(servicio)

            try:
                resultado = await run_supabase(
                    lambda: supabase.table("provider_services").insert({
                        "provider_id": provider_id,
                        "service_name": servicio,
                        "service_name_normalized": servicio_normalizado,
                        "service_embedding": None,  # Sin embedding
                        "is_primary": (idx == 0),
                        "display_order": idx,
                    }).execute(),
                    timeout=timeout,
                    label="provider_services.insert_no_embedding",
                )

                if resultado.data:
                    servicios_insertados.append(resultado.data[0])
                    logger.info(f"✅ Servicio insertado (sin embedding): {servicio}")

            except Exception as e:
                logger.error(f"❌ Error insertando servicio {servicio}: {e}")

        return servicios_insertados

    # Generar embeddings para cada servicio
    for idx, servicio in enumerate(servicios):
        try:
            # Generar embedding individual para este servicio
            logger.info(f"🔄 Generando embedding para servicio: {servicio}")
            embedding = await embeddings_service.generar_embedding(servicio)

            if not embedding:
                logger.warning(f"⚠️ No se pudo generar embedding para servicio: {servicio}")
                continue

            # Normalizar nombre para búsqueda
            servicio_normalizado = normalizar_texto_para_busqueda(servicio)

            # Insertar en provider_services
            resultado = await run_supabase(
                lambda: supabase.table("provider_services").insert({
                    "provider_id": provider_id,
                    "service_name": servicio,
                    "service_name_normalized": servicio_normalizado,
                    "service_embedding": embedding,
                    "is_primary": (idx == 0),  # Primer servicio = principal
                    "display_order": idx,
                }).execute(),
                timeout=timeout,
                label="provider_services.insert_with_embedding",
            )

            if resultado.data:
                servicios_insertados.append(resultado.data[0])
                logger.info(
                    f"✅ Servicio insertado: {servicio} "
                    f"(embedding: {len(embedding)} dims, primary: {idx == 0})"
                )
            else:
                logger.warning(f"⚠️ No se pudo insertar servicio: {servicio}")

        except Exception as e:
            logger.error(f"❌ Error insertando servicio {servicio}: {e}")
            continue

    logger.info(f"✅ Total servicios insertados: {len(servicios_insertados)}/{len(servicios)}")
    return servicios_insertados


async def registrar_proveedor_en_base_datos(
    supabase: Client,
    datos_proveedor: SolicitudCreacionProveedor,
    embeddings_service: Optional[ServicioEmbeddings] = None,
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Registra proveedor usando el esquema unificado simplificado.

    Fase 6: Actualizada para insertar servicios en provider_services con embeddings.

    Esta función realiza las siguientes operaciones:
    1. Normaliza los datos del proveedor
    2. Ejecuta un upsert en la tabla providers (conflicto en campo phone)
    3. Recupera el registro insertado/actualizado
    4. Inserta servicios individuales en provider_services con embeddings
    5. Aplica valores por defecto a campos obligatorios
    6. Actualiza el caché de búsqueda

    Args:
        supabase: Cliente de Supabase
        datos_proveedor: Datos del proveedor a registrar
        embeddings_service: Servicio de embeddings (opcional, Fase 6)
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

            # Fase 6: Insertar servicios en provider_services con embeddings
            servicios = datos_normalizados.get("services_normalized", [])
            if servicios:
                logger.info(f"🔄 Insertando {len(servicios)} servicios en provider_services...")
                servicios_insertados = await insertar_servicios_proveedor(
                    supabase=supabase,
                    provider_id=id_proveedor,
                    servicios=servicios,
                    embeddings_service=embeddings_service,
                    timeout=timeout,
                )
                logger.info(f"✅ Servicios insertados: {len(servicios_insertados)}/{len(servicios)}")
            else:
                logger.warning("⚠️ No hay servicios para insertar en provider_services")

            # Fase 6: Eliminado campo 'profession' del registro
            provider_record = {
                "id": id_proveedor,
                "phone": registro_insertado.get("phone", datos_normalizados["phone"]),
                "full_name": registro_insertado.get(
                    "full_name", datos_normalizados["full_name"]
                ),
                "email": registro_insertado.get("email", datos_normalizados["email"]),
                "city": registro_insertado.get("city", datos_normalizados["city"]),
                # Fase 6: Eliminado campo 'profession'
                "services": registro_insertado.get(
                    "services", datos_normalizados["services"]
                ),
                "services_normalized": datos_normalizados.get("services_normalized", []),
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
            from flows.sesion import cachear_perfil_proveedor

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
