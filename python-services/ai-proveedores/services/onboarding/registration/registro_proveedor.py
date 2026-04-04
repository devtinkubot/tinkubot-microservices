"""Funciones de registro de proveedores en base de datos."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from infrastructure.database import run_supabase
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings
from models.proveedores import SolicitudCreacionProveedor
from services.onboarding.registration.catalogo_servicios import (
    clasificar_servicios_livianos,
    construir_service_summary,
    construir_texto_embedding_canonico,
)
from services.onboarding.registration.constantes import DISPLAY_ORDER_MAX_DB
from services.onboarding.whatsapp_identity import persistir_identities_whatsapp
from services.onboarding.registration.normalizacion import (
    garantizar_campos_obligatorios_proveedor,
    normalizar_datos_proveedor,
)
from supabase import Client
from utils import normalizar_texto_para_busqueda

logger = logging.getLogger(__name__)


def _resolver_display_order(idx: int) -> int:
    """Ajusta display_order al máximo soportado por la tabla."""
    return idx if idx <= DISPLAY_ORDER_MAX_DB else DISPLAY_ORDER_MAX_DB


def _normalizar_entradas_servicio(servicios: List[Any]) -> List[Dict[str, Any]]:
    """Convierte la entrada de servicios en un payload uniforme para persistencia."""
    entradas: List[Dict[str, str]] = []
    for servicio in servicios:
        if isinstance(servicio, dict):
            nombre_visible = str(servicio.get("service_name") or "").strip()
            texto_original = str(
                servicio.get("raw_service_text") or nombre_visible
            ).strip()
            service_summary = str(servicio.get("service_summary") or "").strip()
            domain_code = str(servicio.get("domain_code") or "").strip() or None
            category_name = str(servicio.get("category_name") or "").strip() or None
            classification_confidence = servicio.get("classification_confidence")
            requires_review = servicio.get("requires_review")
            review_reason = servicio.get("review_reason")
        else:
            nombre_visible = str(servicio or "").strip()
            texto_original = nombre_visible
            service_summary = ""
            domain_code = None
            category_name = None
            classification_confidence = None
            requires_review = None
            review_reason = None

        if not nombre_visible:
            continue

        entradas.append(
            {
                "service_name": nombre_visible,
                "raw_service_text": texto_original or nombre_visible,
                "service_summary": service_summary,
                "domain_code": domain_code,
                "category_name": category_name,
                "classification_confidence": classification_confidence,
                "requires_review": requires_review,
                "review_reason": review_reason,
            }
        )
    return entradas


def _clasificacion_servicio_completa(clasificacion: Dict[str, Any]) -> bool:
    return bool(
        str(clasificacion.get("domain_resolution_status") or "").strip().lower()
        == "matched"
        and str(clasificacion.get("resolved_domain_code") or "").strip()
        and str(clasificacion.get("category_name") or "").strip()
        and bool(clasificacion.get("is_valid_service", True))
        and not bool(clasificacion.get("needs_clarification"))
    )


async def asegurar_proveedor_borrador(
    supabase: Client,
    telefono: str,
    tiempo_espera: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """Crea o recupera un proveedor borrador para iniciar onboarding.

    Este registro existe solo para materializar el `provider_id` temprano.
    No marca consentimiento ni el onboarding completo como finalizado.
    """
    if not supabase:
        return None

    telefono_normalizado = str(telefono or "").strip()
    if not telefono_normalizado:
        return None

    payload_borrador = {
        "phone": telefono_normalizado,
        "full_name": "",
        "city": "",
        "status": "pending",
        "has_consent": False,
        "experience_range": None,
        "updated_at": datetime.utcnow().isoformat(),
    }

    resultado = await run_supabase(
        lambda: supabase.table("providers")
        .upsert(payload_borrador, on_conflict="phone")
        .execute(),
        timeout=tiempo_espera,
        label="providers.upsert_draft",
    )
    error_resultado = getattr(resultado, "error", None)
    if error_resultado:
        logger.error("❌ Supabase rechazó el borrador: %s", error_resultado)
        return None

    registro_borrador: Optional[Dict[str, Any]] = None
    datos_resultado = getattr(resultado, "data", None)
    if isinstance(datos_resultado, list) and datos_resultado:
        registro_borrador = datos_resultado[0]
    elif isinstance(datos_resultado, dict) and datos_resultado:
        registro_borrador = datos_resultado

    if registro_borrador is None:
        try:
            reconsulta = await run_supabase(
                lambda: supabase.table("providers")
                .select("*")
                .eq("phone", telefono_normalizado)
                .limit(1)
                .execute(),
                timeout=tiempo_espera,
                label="providers.fetch_draft_after_upsert",
            )
            if reconsulta.data:
                registro_borrador = reconsulta.data[0]
        except Exception as error_reconsulta:
            logger.warning(
                "⚠️ No se pudo recuperar borrador del proveedor: %s",
                error_reconsulta,
            )

    return registro_borrador


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
    tiene_embeddings = bool(
        servicio_embeddings and hasattr(servicio_embeddings, "generar_embedding")
    )
    clasificaciones_semanticas = await clasificar_servicios_livianos(
        cliente_openai=getattr(servicio_embeddings, "client", None),
        supabase=supabase,
        servicios=[entry["service_name"] for entry in service_entries],
    )

    clasificaciones_incompletas: List[Dict[str, Any]] = []
    for idx, entry in enumerate(service_entries):
        metadata_base = (
            clasificaciones_semanticas[idx]
            if idx < len(clasificaciones_semanticas)
            else {}
        )
        if not _clasificacion_servicio_completa(metadata_base):
            clasificaciones_incompletas.append(
                {
                    "service": entry["service_name"],
                    "error": "classification_incomplete",
                    "reason": metadata_base.get("reason"),
                    "response": metadata_base.get("clarification_question"),
                }
            )

    if clasificaciones_incompletas:
        logger.warning(
            "⚠️ No se insertan servicios porque la clasificación no cerró: %s",
            clasificaciones_incompletas,
        )
        return {
            "inserted_rows": [],
            "requested_count": requested_count,
            "inserted_count": 0,
            "failed_services": clasificaciones_incompletas,
        }

    def _resultado() -> Dict[str, Any]:
        return {
            "inserted_rows": servicios_insertados,
            "requested_count": requested_count,
            "inserted_count": len(servicios_insertados),
            "failed_services": failed_services,
        }

    if not tiene_embeddings:
        logger.warning(
            "⚠️ Servicio de embeddings no disponible, no se generarán embeddings"
        )
        # Si no hay servicio de embeddings, igual insertamos los servicios sin embedding
        for idx, entry in enumerate(service_entries):
            servicio = entry["service_name"]
            servicio_normalizado = normalizar_texto_para_busqueda(servicio)
            metadata_base = (
                clasificaciones_semanticas[idx]
                if idx < len(clasificaciones_semanticas)
                else {}
            )
            metadata = {**entry, **metadata_base}
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

            if not domain_code_to_use or not metadata.get("category_name"):
                failed_services.append(
                    {
                        "service": servicio,
                        "error": "missing_domain_or_category",
                    }
                )
                continue

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
                            "classification_confidence": (
                                metadata.get("classification_confidence") or 0.0
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
            servicio_normalizado = normalizar_texto_para_busqueda(servicio)
            metadata_base = (
                clasificaciones_semanticas[idx]
                if idx < len(clasificaciones_semanticas)
                else {}
            )
            metadata = {**entry, **metadata_base}
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
                construir_texto_embedding_canonico(
                    service_summary=service_summary,
                    domain_code=domain_code_to_use,
                    category_name=metadata.get("category_name"),
                )
            )

            if not embedding:
                logger.warning(
                    f"⚠️ No se pudo generar embedding para servicio: {servicio}"
                )
                embedding = None

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
                        "domain_code": domain_code_to_use,
                        "category_name": metadata.get("category_name"),
                        "classification_confidence": (
                            metadata.get("classification_confidence") or 0.0
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
        account_id = datos_normalizados.pop("account_id", None)
        from_number = datos_normalizados.pop("from_number", None)
        user_id = datos_normalizados.pop("user_id", None)

        # Upsert por teléfono: reabre rechazados como pending, evita doble round-trip
        carga_upsert = {
            **datos_normalizados,
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

            try:
                await persistir_identities_whatsapp(
                    supabase,
                    str(id_proveedor or "").strip(),
                    phone=datos_normalizados.get("phone"),
                    from_number=from_number,
                    user_id=user_id,
                    account_id=account_id,
                )
            except Exception as exc:
                logger.warning(
                    "⚠️ No se pudieron persistir identidades WhatsApp para %s: %s",
                    id_proveedor,
                    exc,
                )

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
                if resultado_insercion["inserted_count"] != resultado_insercion["requested_count"]:
                    logger.warning(
                        "⚠️ Registro detenido porque no se pudieron cerrar todos los servicios"
                    )
                    return {
                        "id": id_proveedor,
                        "phone": registro_insertado.get("phone", datos_normalizados["phone"]),
                        "registration_blocked_reason": "service_classification_incomplete",
                        "error_reason": "service_classification_incomplete",
                        "services_normalized": servicios_normalizados,
                        "service_entries": service_entries,
                        "failed_services": resultado_insercion["failed_services"],
                    }
            else:
                logger.warning("⚠️ No hay servicios para insertar en provider_services")

            try:
                await run_supabase(
                    lambda: supabase.table("providers")
                    .update(
                        {
                            "onboarding_complete": True,
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    )
                    .eq("id", id_proveedor)
                    .execute(),
                    timeout=tiempo_espera,
                    label="providers.mark_onboarding_complete",
                )
            except Exception as exc:
                logger.warning(
                    "⚠️ No se pudo marcar onboarding_complete para %s: %s",
                    id_proveedor,
                    exc,
                )

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
                "document_first_names": registro_insertado.get(
                    "document_first_names",
                    datos_normalizados.get("document_first_names"),
                ),
                "document_last_names": registro_insertado.get(
                    "document_last_names",
                    datos_normalizados.get("document_last_names"),
                ),
                "document_id_number": registro_insertado.get(
                    "document_id_number",
                    datos_normalizados.get("document_id_number"),
                ),
                "city": registro_insertado.get("city", datos_normalizados["city"]),
                # Fase 6: Eliminado campo 'profession'
                "services_normalized": servicios_normalizados,
                "service_entries": service_entries,
                "experience_range": registro_insertado.get(
                    "experience_range", datos_normalizados.get("experience_range")
                ),
                "onboarding_complete": registro_insertado.get(
                    "onboarding_complete",
                    datos_normalizados.get("onboarding_complete"),
                ),
                "rating": registro_insertado.get(
                    "rating", datos_normalizados["rating"]
                ),
                "has_consent": registro_insertado.get(
                    "has_consent", datos_normalizados["has_consent"]
                ),
                "display_name": registro_insertado.get(
                    "display_name", datos_normalizados.get("display_name")
                ),
                "formatted_name": registro_insertado.get(
                    "formatted_name", datos_normalizados.get("formatted_name")
                ),
                "first_name": registro_insertado.get(
                    "first_name", datos_normalizados.get("first_name")
                ),
                "last_name": registro_insertado.get(
                    "last_name", datos_normalizados.get("last_name")
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
            from services.onboarding.session import (
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
