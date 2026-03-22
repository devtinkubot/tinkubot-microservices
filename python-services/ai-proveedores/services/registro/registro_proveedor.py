"""Funciones de registro de proveedores en base de datos."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from infrastructure.database import run_supabase
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from models.proveedores import SolicitudCreacionProveedor
from services.registro.normalizacion import (
    garantizar_campos_obligatorios_proveedor,
    normalizar_datos_proveedor,
)
from services.servicios_proveedor.clasificacion_semantica import (
    clasificar_servicios_livianos,
    construir_service_summary,
)
from services.servicios_proveedor.constantes import DISPLAY_ORDER_MAX_DB
from services.servicios_proveedor.utilidades import normalizar_texto_para_busqueda
from supabase import Client

logger = logging.getLogger(__name__)


def _resolver_display_order(idx: int) -> int:
    """Ajusta display_order al máximo soportado por la tabla."""
    return idx if idx <= DISPLAY_ORDER_MAX_DB else DISPLAY_ORDER_MAX_DB


def _normalizar_entradas_servicio(servicios: List[Any]) -> List[Dict[str, str]]:
    """Convierte la entrada de servicios en un payload uniforme para persistencia."""
    entradas: List[Dict[str, str]] = []
    for servicio in servicios:
        if isinstance(servicio, dict):
            nombre_visible = str(servicio.get("service_name") or "").strip()
            texto_original = str(
                servicio.get("raw_service_text") or nombre_visible
            ).strip()
            service_summary = str(servicio.get("service_summary") or "").strip()
        else:
            nombre_visible = str(servicio or "").strip()
            texto_original = nombre_visible
            service_summary = ""

        if not nombre_visible:
            continue

        entradas.append(
            {
                "service_name": nombre_visible,
                "raw_service_text": texto_original or nombre_visible,
                "service_summary": service_summary,
            }
        )
    return entradas


async def insertar_servicios_proveedor(
    supabase: Client,
    proveedor_id: str,
    servicios: List[Any],
    servicio_embeddings: Optional[ServicioEmbeddings],
    tiempo_espera: float = 5.0,
    display_order_start: int = 0,
    mark_first_as_primary: bool = True,
) -> Dict[str, Any]:
    """
    Inserta servicios individuales en provider_services con embeddings.

    Fase 6: Nueva función para gestionar la inserción de servicios con embeddings
    en la tabla provider_services. Cada servicio se inserta individualmente con
    su propio embedding vectorial para búsquedas semánticas.

    Args:
        supabase: Cliente de Supabase
        proveedor_id: ID del proveedor
        servicios: Lista de servicios visibles o payloads con texto original
        servicio_embeddings: Servicio para generar embeddings (opcional)
        tiempo_espera: Timeout para operaciones de Supabase (segundos)

    Returns:
        Dict con conteos y detalle de errores:
        - inserted_rows: Filas insertadas en provider_services
        - requested_count: Cantidad solicitada
        - inserted_count: Cantidad insertada
        - failed_services: Lista de errores por servicio

    Example:
        >>> servicios = ["Plomería", "Electricidad", "Gasfitería"]
        >>> insertados = await insertar_servicios_proveedor(
        ...     supabase, "prov-123", servicios, servicio_embeddings
        ... )
        >>> print(insertados["inserted_count"])  # 3
    """
    servicios_insertados: List[Dict[str, Any]] = []
    failed_services: List[Dict[str, str]] = []
    service_entries = _normalizar_entradas_servicio(servicios)
    requested_count = len(service_entries)
    clasificaciones_semanticas = await clasificar_servicios_livianos(
        cliente_openai=getattr(servicio_embeddings, "client", None),
        supabase=supabase,
        servicios=[entry["service_name"] for entry in service_entries],
    )

    def _resultado() -> Dict[str, Any]:
        return {
            "inserted_rows": servicios_insertados,
            "requested_count": requested_count,
            "inserted_count": len(servicios_insertados),
            "failed_services": failed_services,
        }

    if not servicio_embeddings:
        logger.warning(
            "⚠️ Servicio de embeddings no disponible, no se generarán embeddings"
        )
        # Si no hay servicio de embeddings, igual insertamos los servicios sin embedding
        for idx, entry in enumerate(service_entries):
            servicio = entry["service_name"]
            servicio_normalizado = normalizar_texto_para_busqueda(servicio)
            metadata = (
                clasificaciones_semanticas[idx]
                if idx < len(clasificaciones_semanticas)
                else {}
            )
            # ✅ Usar dominio sugerido si no hay match exacto
            # El servicio se inserta aunque requiera revisión de catálogo
            domain_code_to_use = metadata.get("resolved_domain_code") or metadata.get(
                "domain_code"
            )

            service_summary = (
                entry.get("service_summary")
                or metadata.get("service_summary")
                or construir_service_summary(
                    service_name=servicio,
                    category_name=metadata.get("category_name"),
                    domain_code=domain_code_to_use,
                )
            )

            try:
                resultado = await run_supabase(
                    lambda: supabase.table("provider_services")
                    .insert(
                        {
                            "provider_id": proveedor_id,
                            "service_name": servicio,
                            "raw_service_text": entry["raw_service_text"],
                            "service_summary": service_summary,
                            "service_name_normalized": servicio_normalizado,
                            "service_embedding": None,  # Sin embedding
                            "is_primary": mark_first_as_primary and (idx == 0),
                            "display_order": _resolver_display_order(
                                display_order_start + idx
                            ),
                            # Usar dominio sugerido.
                            "domain_code": domain_code_to_use,
                            "category_name": metadata.get("category_name"),
                            "classification_confidence": metadata.get(
                                "classification_confidence", 0.0
                            ),
                        }
                    )
                    .execute(),
                    timeout=tiempo_espera,
                    label="provider_services.insert_no_embedding",
                )
                if resultado.data:
                    servicios_insertados.append(resultado.data[0])
                    logger.info(
                        "✅ Servicio insertado (sin embedding): %s",
                        servicio,
                    )

                else:
                    failed_services.append(
                        {
                            "service": servicio,
                            "error": "insert_without_data",
                        }
                    )
            except Exception as exc:
                logger.error("❌ Error insertando servicio %s: %s", servicio, exc)
                failed_services.append(
                    {
                        "service": servicio,
                        "error": str(exc),
                    }
                )

        return _resultado()

    # Generar embeddings para cada servicio
    for idx, entry in enumerate(service_entries):
        try:
            servicio = entry["service_name"]
            metadata = (
                clasificaciones_semanticas[idx]
                if idx < len(clasificaciones_semanticas)
                else {}
            )
            # ✅ Usar dominio sugerido si no hay match exacto
            # El servicio se inserta aunque requiera revisión de catálogo
            domain_code_to_use = metadata.get("resolved_domain_code") or metadata.get(
                "domain_code"
            )

            service_summary = (
                entry.get("service_summary")
                or metadata.get("service_summary")
                or construir_service_summary(
                    service_name=servicio,
                    category_name=metadata.get("category_name"),
                    domain_code=domain_code_to_use,
                )
            )
            # Generar embedding individual para este servicio
            logger.info(f"🔄 Generando embedding para servicio: {servicio}")
            embedding = await servicio_embeddings.generar_embedding(
                f"{servicio}. {service_summary}".strip()
            )

            if not embedding:
                logger.warning(
                    f"⚠️ No se pudo generar embedding para servicio: {servicio}"
                )
                embedding = None

            # Normalizar nombre para búsqueda
            servicio_normalizado = normalizar_texto_para_busqueda(servicio)

            # Insertar en provider_services
            resultado = await run_supabase(
                lambda: supabase.table("provider_services")
                .insert(
                    {
                        "provider_id": proveedor_id,
                        "service_name": servicio,
                        "raw_service_text": entry["raw_service_text"],
                        "service_summary": service_summary,
                        "service_name_normalized": servicio_normalizado,
                        "service_embedding": embedding,
                        "is_primary": mark_first_as_primary
                        and (idx == 0),  # Primer servicio = principal
                        "display_order": _resolver_display_order(
                            display_order_start + idx
                        ),
                        "domain_code": domain_code_to_use,  # ✅ Usar dominio sugerido
                        "category_name": metadata.get("category_name"),
                        "classification_confidence": metadata.get(
                            "classification_confidence", 0.0
                        ),
                    }
                )
                .execute(),
                timeout=tiempo_espera,
                label="provider_services.insert_with_embedding",
            )
            if resultado.data:
                servicios_insertados.append(resultado.data[0])
                embedding_dims = len(embedding) if embedding else 0
                logger.info(
                    f"✅ Servicio insertado: {servicio} "
                    f"(embedding: {embedding_dims} dims, primary: "
                    f"{mark_first_as_primary and (idx == 0)})"
                )
            else:
                logger.warning(f"⚠️ No se pudo insertar servicio: {servicio}")
                failed_services.append(
                    {
                        "service": servicio,
                        "error": "insert_without_data",
                    }
                )

        except Exception as exc:
            logger.error("❌ Error insertando servicio %s: %s", servicio, exc)
            failed_services.append(
                {
                    "service": servicio,
                    "error": str(exc),
                }
            )
            continue

    logger.info(
        "✅ Total servicios insertados: %s/%s (fallidos=%s)",
        len(servicios_insertados),
        len(service_entries),
        len(failed_services),
    )
    return _resultado()


async def registrar_proveedor_en_base_datos(
    supabase: Client,
    datos_proveedor: SolicitudCreacionProveedor,
    servicio_embeddings: Optional[ServicioEmbeddings] = None,
    tiempo_espera: float = 5.0,
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
        servicio_embeddings: Servicio de embeddings (opcional, Fase 6)
        tiempo_espera: Timeout para operaciones de Supabase (segundos)

    Returns:
        Dict con el proveedor registrado o None si falló
    """
    if not supabase:
        return None

    try:
        # Normalizar datos
        datos_normalizados = normalizar_datos_proveedor(datos_proveedor)
        servicios_normalizados = datos_normalizados.pop("services_normalized", [])
        service_entries = datos_normalizados.pop("service_entries", [])

        # Upsert por teléfono: reabre rechazados como pending, evita doble round-trip
        carga_upsert = {
            **datos_normalizados,
            "verified": False,
            "updated_at": datetime.utcnow().isoformat(),
        }

        resultado = await run_supabase(
            lambda: supabase.table("providers")
            .upsert(carga_upsert, on_conflict="phone")
            .execute(),
            timeout=tiempo_espera,
            label="providers.upsert",
        )
        error_resultado = getattr(resultado, "error", None)
        if error_resultado:
            logger.error("❌ Supabase rechazó el registro/upsert: %s", error_resultado)
            return None

        registro_insertado: Optional[Dict[str, Any]] = None
        datos_resultado = getattr(resultado, "data", None)
        if isinstance(datos_resultado, list) and datos_resultado:
            registro_insertado = datos_resultado[0]
        elif isinstance(datos_resultado, dict) and datos_resultado:
            registro_insertado = datos_resultado

        # Algunos proyectos usan Prefer: return=minimal, hacer fetch adicional
        if registro_insertado is None:
            try:
                reconsulta = await run_supabase(
                    lambda: supabase.table("providers")
                    .select("*")
                    .eq("phone", datos_normalizados["phone"])
                    .limit(1)
                    .execute(),
                    timeout=tiempo_espera,
                    label="providers.fetch_after_upsert",
                )
                if reconsulta.data:
                    registro_insertado = reconsulta.data[0]
            except Exception as error_reconsulta:
                logger.warning(
                    "⚠️ No se pudo recuperar proveedor recién creado: %s",
                    error_reconsulta,
                )

        if registro_insertado:
            id_proveedor = registro_insertado.get("id")
            logger.info(f"✅ Proveedor registrado en esquema unificado: {id_proveedor}")

            # Fase 6: Insertar servicios en provider_services con embeddings
            servicios = service_entries or servicios_normalizados
            if servicios:
                logger.info(
                    "🔄 Insertando %s servicios en provider_services...",
                    len(servicios),
                )
                resultado_insercion = await insertar_servicios_proveedor(
                    supabase=supabase,
                    proveedor_id=id_proveedor,
                    servicios=servicios,
                    servicio_embeddings=servicio_embeddings,
                    tiempo_espera=tiempo_espera,
                )
                logger.info(
                    "✅ Servicios insertados: %s/%s (fallidos=%s)",
                    resultado_insercion["inserted_count"],
                    resultado_insercion["requested_count"],
                    len(resultado_insercion["failed_services"]),
                )
            else:
                logger.warning("⚠️ No hay servicios para insertar en provider_services")

            # Fase 6: Eliminado campo 'profession' del registro
            registro_proveedor = {
                "id": id_proveedor,
                "phone": registro_insertado.get("phone", datos_normalizados["phone"]),
                "real_phone": registro_insertado.get(
                    "real_phone", datos_normalizados.get("real_phone")
                ),
                "full_name": registro_insertado.get(
                    "full_name", datos_normalizados["full_name"]
                ),
                "city": registro_insertado.get("city", datos_normalizados["city"]),
                # Fase 6: Eliminado campo 'profession'
                "services_normalized": servicios_normalizados,
                "service_entries": service_entries,
                "experience_years": registro_insertado.get(
                    "experience_years", datos_normalizados["experience_years"]
                ),
                "rating": registro_insertado.get(
                    "rating", datos_normalizados["rating"]
                ),
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
                "facebook_username": registro_insertado.get(
                    "facebook_username", datos_normalizados.get("facebook_username")
                ),
                "instagram_username": registro_insertado.get(
                    "instagram_username", datos_normalizados.get("instagram_username")
                ),
                "created_at": registro_insertado.get(
                    "created_at", datetime.now().isoformat()
                ),
            }

            perfil_normalizado = garantizar_campos_obligatorios_proveedor(
                registro_proveedor
            )
            # Importar localmente para evitar ciclo de importación
            from flows.sesion import (
                cachear_perfil_proveedor,
                limpiar_marca_perfil_eliminado,
            )

            telefono_perfil = perfil_normalizado.get(
                "phone", datos_normalizados["phone"]
            )
            await limpiar_marca_perfil_eliminado(telefono_perfil)

            await cachear_perfil_proveedor(
                telefono_perfil,
                perfil_normalizado,
            )
            return perfil_normalizado
        else:
            logger.error("❌ No se pudo registrar proveedor")
            return None

    except Exception as e:
        logger.error(f"❌ Error en registrar_proveedor_en_base_datos: {e}")
        return None
