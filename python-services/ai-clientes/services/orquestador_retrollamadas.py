"""Retrollamadas para el orquestador conversacional."""

import asyncio
from typing import Any, Dict

from infrastructure.database import run_supabase
from services.proveedores.conexion import (
    mensaje_conexion_formal as construir_mensaje_conexion_formal,
)


class OrquestadorRetrollamadas:
    def __init__(
        self,
        *,
        supabase,
        repositorio_flujo,
        repositorio_clientes,
        buscador,
        moderador_contenido,
        programador_retroalimentacion,
        logger,
        supabase_bucket: str,
        supabase_base_url: str,
    ) -> None:
        self.supabase = supabase
        self.repositorio_flujo = repositorio_flujo
        self.repositorio_clientes = repositorio_clientes
        self.buscador = buscador
        self.moderador_contenido = moderador_contenido
        self.programador_retroalimentacion = programador_retroalimentacion
        self.logger = logger
        self.supabase_bucket = supabase_bucket
        self.supabase_base_url = supabase_base_url

    async def obtener_o_crear_cliente(self, telefono: str):
        if self.repositorio_clientes:
            return await self.repositorio_clientes.obtener_o_crear(telefono=telefono) or {}
        if not self.supabase:
            return {}
        try:
            respuesta = await run_supabase(
                lambda: self.supabase.table("customers")
                .select("*")
                .eq("phone_number", telefono)
                .limit(1)
                .execute(),
                etiqueta="get_customer",
            )
            if respuesta.data and len(respuesta.data) > 0:
                return respuesta.data[0]
            respuesta = await run_supabase(
                lambda: self.supabase.table("customers")
                .insert({"phone_number": telefono, "has_consent": False})
                .execute(),
                etiqueta="create_customer",
            )
            return respuesta.data[0] if respuesta.data else {}
        except Exception as exc:
            self.logger.error(f"Error en obtener_o_crear_cliente: {exc}")
            return {}

    async def solicitar_consentimiento(self, telefono: str):
        from templates.mensajes.consentimiento import mensajes_flujo_consentimiento

        flujo = (
            await self.repositorio_flujo.obtener(telefono)
            if self.repositorio_flujo
            else {}
        )
        flujo["state"] = "awaiting_consent"
        if self.repositorio_flujo:
            await self.repositorio_flujo.guardar(telefono, flujo)
        mensajes = mensajes_flujo_consentimiento()
        return {
            "messages": [{"response": msg} for msg in mensajes]
        }

    async def manejar_respuesta_consentimiento(
        self,
        telefono: str,
        perfil_cliente: Dict[str, Any],
        opcion_seleccionada: str = None,
        carga: Dict[str, Any] = None,
    ):
        opcion_normalizada = (opcion_seleccionada or "").strip().strip("*").rstrip(".)")
        if opcion_normalizada in {"1", "2"}:
            acepta = opcion_normalizada == "1"
            if acepta:
                if self.repositorio_clientes and perfil_cliente:
                    await self.repositorio_clientes.actualizar_consentimiento(
                        perfil_cliente.get("id"),
                        True,
                    )
                elif self.supabase:
                    try:
                        await run_supabase(
                            lambda: self.supabase.table("customers")
                            .update({"has_consent": True})
                            .eq("phone_number", telefono)
                            .execute(),
                            etiqueta="update_consent",
                        )
                    except Exception as exc:
                        self.logger.error(f"Error actualizando consentimiento: {exc}")
                return {
                    "messages": [
                        {
                            "response": "*¡Gracias por aceptar!* Ahora cuéntame, ¿qué necesitas?"
                        }
                    ]
                }
            return {
                "messages": [
                    {
                        "response": "Entendido. Sin tu consentimiento no puedo procesar tu solicitud."
                    }
                ]
            }
        return {}

    async def resetear_flujo(self, telefono: str):
        if self.repositorio_flujo:
            await self.repositorio_flujo.guardar(
                telefono, {"state": "awaiting_service"}
            )

    async def obtener_flujo(self, telefono: str):
        if self.repositorio_flujo:
            return await self.repositorio_flujo.obtener(telefono) or {}
        return {}

    async def guardar_flujo(self, telefono: str, datos: dict):
        if self.repositorio_flujo:
            await self.repositorio_flujo.guardar(telefono, datos)

    async def actualizar_ciudad_cliente(
        self, cliente_id: str, ciudad: str, ciudad_confirmada_en: str = None
    ):
        if self.repositorio_clientes:
            await self.repositorio_clientes.actualizar_ciudad(cliente_id, ciudad)
            return
        if not self.supabase:
            return
        try:
            datos_actualizacion = {"city": ciudad}
            if ciudad_confirmada_en:
                datos_actualizacion["city_confirmed_at"] = ciudad_confirmada_en
            await run_supabase(
                lambda: self.supabase.table("customers")
                .update(datos_actualizacion)
                .eq("id", cliente_id)
                .execute(),
                etiqueta="update_city",
            )
        except Exception as exc:
            self.logger.error(f"Error en actualizar_ciudad_cliente: {exc}")

    async def buscar_proveedores(
        self,
        servicio: str,
        ciudad: str,
        radio_km: float = 10.0,
        descripcion_problema: str | None = None,
        limite: int = 10,
    ):
        if self.buscador:
            resultado = await self.buscador.buscar(
                profesion=servicio,
                ciudad=ciudad,
                radio_km=radio_km,
                descripcion_problema=descripcion_problema or servicio,
            )
            return resultado.get("results", []) if resultado else []
        return []

    async def enviar_prompt_proveedor(self, telefono: str, flujo: dict, ciudad: str):
        """Construye y retorna el listado de proveedores para WhatsApp."""
        from templates.proveedores.detalle import instruccion_seleccionar_proveedor
        from templates.proveedores.listado import (
            bloque_listado_proveedores_compacto,
            mensaje_intro_listado_proveedores,
            mensaje_listado_sin_resultados,
        )

        proveedores = (flujo or {}).get("providers") or []
        ciudad_texto = ciudad or (flujo or {}).get("city") or ""

        if not proveedores:
            self.logger.warning(
                f"Sin proveedores en flujo al enviar prompt para {telefono} (city={ciudad_texto})"
            )
            return {"response": mensaje_listado_sin_resultados(ciudad_texto)}

        intro = mensaje_intro_listado_proveedores(ciudad_texto)
        bloque = bloque_listado_proveedores_compacto(proveedores)
        mensaje = f"{intro}\n\n{bloque}\n{instruccion_seleccionar_proveedor}"
        return {"response": mensaje}

    async def enviar_prompt_confirmacion(
        self, telefono: str, flujo: dict, titulo: str = None
    ):
        """Construye y retorna el prompt de confirmación de nueva búsqueda."""
        from templates.busqueda.confirmacion import (
            mensajes_confirmacion_busqueda,
            titulo_confirmacion_repetir_busqueda,
        )

        incluir_opcion_ciudad = bool((flujo or {}).get("confirm_include_city_option"))
        titulo_final = (
            titulo
            or (flujo or {}).get("confirm_title")
            or titulo_confirmacion_repetir_busqueda
        )

        self.logger.info(
            "Enviando prompt confirmación para %s (titulo=%s, opcion_ciudad=%s)",
            telefono,
            titulo_final,
            incluir_opcion_ciudad,
        )
        return {
            "messages": mensajes_confirmacion_busqueda(
                titulo_final, incluir_opcion_ciudad=incluir_opcion_ciudad
            )
        }

    def limpiar_ciudad_cliente(self, cliente_id: str):
        if self.repositorio_clientes and cliente_id:
            try:
                asyncio.create_task(
                    self.repositorio_clientes.limpiar_ciudad(cliente_id)
                )
            except Exception:
                return None
        return None

    def limpiar_consentimiento_cliente(self, cliente_id: str):
        if self.repositorio_clientes and cliente_id:
            try:
                asyncio.create_task(
                    self.repositorio_clientes.limpiar_consentimiento(cliente_id)
                )
            except Exception:
                return None
        return None

    async def mensaje_conexion_formal(
        self, proveedor: Dict[str, Any]
    ) -> Dict[str, Any]:
        return construir_mensaje_conexion_formal(
            proveedor,
            supabase=self.supabase,
            bucket=self.supabase_bucket,
            supabase_base_url=self.supabase_base_url,
        )

    async def programar_solicitud_retroalimentacion(
        self, telefono: str, proveedor: Dict[str, Any]
    ):
        if self.programador_retroalimentacion:
            await self.programador_retroalimentacion.programar_solicitud_retroalimentacion(
                telefono, proveedor
            )

    async def enviar_texto_whatsapp(self, telefono: str, texto: str) -> bool:
        if self.programador_retroalimentacion:
            return await self.programador_retroalimentacion.enviar_texto_whatsapp(
                telefono, texto
            )
        return False

    async def verificar_si_bloqueado(self, telefono: str) -> bool:
        if not self.moderador_contenido:
            return False
        return await self.moderador_contenido.verificar_si_bloqueado(telefono)

    async def validar_contenido_con_ia(self, texto: str, telefono: str):
        if not self.moderador_contenido:
            return None, None
        return await self.moderador_contenido.validar_contenido_con_ia(texto, telefono)

    def build(self) -> Dict[str, Any]:
        return {
            "obtener_o_crear_cliente": self.obtener_o_crear_cliente,
            "solicitar_consentimiento": self.solicitar_consentimiento,
            "manejar_respuesta_consentimiento": self.manejar_respuesta_consentimiento,
            "resetear_flujo": self.resetear_flujo,
            "obtener_flujo": self.obtener_flujo,
            "guardar_flujo": self.guardar_flujo,
            "actualizar_ciudad_cliente": self.actualizar_ciudad_cliente,
            "verificar_si_bloqueado": self.verificar_si_bloqueado,
            "validar_contenido_con_ia": self.validar_contenido_con_ia,
            "buscar_proveedores": self.buscar_proveedores,
            "enviar_prompt_proveedor": self.enviar_prompt_proveedor,
            "enviar_prompt_confirmacion": self.enviar_prompt_confirmacion,
            "limpiar_ciudad_cliente": self.limpiar_ciudad_cliente,
            "limpiar_consentimiento_cliente": self.limpiar_consentimiento_cliente,
            "mensaje_conexion_formal": self.mensaje_conexion_formal,
            "programar_solicitud_retroalimentacion": self.programar_solicitud_retroalimentacion,
            "enviar_texto_whatsapp": self.enviar_texto_whatsapp,
        }
