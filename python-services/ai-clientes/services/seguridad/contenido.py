"""Validación de contenido y gestión de baneo."""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from config.configuracion import configuracion
from templates.mensajes.validacion import (
    mensaje_advertencia_contenido_ilegal,
    mensaje_ban_usuario,
    mensaje_error_input_sin_sentido,
)


def _safe_json_loads(carga: str) -> Optional[Dict[str, Any]]:
    if not carga:
        return None
    try:
        return json.loads(carga)
    except json.JSONDecodeError:
        coincidencia = re.search(r"\{.*\}", carga, re.DOTALL)
        if coincidencia:
            try:
                return json.loads(coincidencia.group(0))
            except json.JSONDecodeError:
                return None
        return None


class ModeradorContenido:
    """Valida contenido con IA y aplica bans temporales."""

    # Modelo configurable vía configuración centralizada
    MODELO_VALIDACION = (
        configuracion.modelo_validacion
        or configuracion.openai_chat_model
        or "gpt-4o-mini"
    )

    def __init__(
        self,
        *,
        redis_client,
        cliente_openai,
        semaforo_openai,
        tiempo_espera_openai: float,
        logger,
    ) -> None:
        self.redis_client = redis_client
        self.cliente_openai = cliente_openai
        self.semaforo_openai = semaforo_openai
        self.tiempo_espera_openai = tiempo_espera_openai
        self.logger = logger

    async def verificar_si_bloqueado(self, telefono: str) -> bool:
        try:
            datos_ban = await self.redis_client.get(f"ban:{telefono}")
            return bool(datos_ban)
        except Exception as exc:
            self.logger.warning(f"⚠️ Error verificando ban para {telefono}: {exc}")
            return False

    async def _record_warning(self, telefono: str, ofensa: str) -> None:
        try:
            clave = f"warnings:{telefono}"
            existente = await self.redis_client.get(clave) or {}
            existente = existente if isinstance(existente, dict) else {}

            existente["count"] = existente.get("count", 0) + 1
            existente["last_warning_at"] = datetime.utcnow().isoformat()
            existente["last_offense"] = ofensa

            await self.redis_client.set(clave, existente, expire=900)
            self.logger.info(
                f"⚠️ Advertencia registrada para {telefono}: {ofensa} (total: {existente['count']})"
            )
        except Exception as exc:
            self.logger.warning(f"⚠️ Error registrando warning para {telefono}: {exc}")

    async def _record_ban(self, telefono: str, razon: str) -> None:
        try:
            datos_ban = {
                "banned_at": datetime.utcnow().isoformat(),
                "reason": razon,
                "offense_count": 2,
                "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat(),
            }
            await self.redis_client.set(f"ban:{telefono}", datos_ban, expire=900)
            self.logger.info(f"🚫 Ban registrado para {telefono}: {razon}")
        except Exception as exc:
            self.logger.warning(f"⚠️ Error registrando ban para {telefono}: {exc}")

    async def _get_warning_count(self, telefono: str) -> int:
        try:
            datos = await self.redis_client.get(f"warnings:{telefono}")
            if datos and isinstance(datos, dict):
                return datos.get("count", 0)
            return 0
        except Exception as exc:
            self.logger.warning(f"⚠️ Error obteniendo warning count para {telefono}: {exc}")
            return 0

    async def _call_openai(
        self, *, prompt_sistema: str, prompt_usuario: str
    ) -> Optional[str]:
        if not self.cliente_openai:
            return None
        try:
            if self.semaforo_openai:
                async with self.semaforo_openai:
                    respuesta = await asyncio.wait_for(
                        self.cliente_openai.chat.completions.create(
                            model=self.MODELO_VALIDACION,
                            messages=[
                                {"role": "system", "content": prompt_sistema},
                                {"role": "user", "content": prompt_usuario},
                            ],
                            temperature=0.3,
                            max_tokens=150,
                        ),
                        timeout=self.tiempo_espera_openai,
                    )
            else:
                respuesta = await asyncio.wait_for(
                    self.cliente_openai.chat.completions.create(
                        model=self.MODELO_VALIDACION,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario},
                        ],
                        temperature=0.3,
                        max_tokens=150,
                    ),
                    timeout=self.tiempo_espera_openai,
                )
            if not respuesta.choices:
                return None
            contenido = (respuesta.choices[0].message.content or "").strip()
            if contenido.startswith("```"):
                contenido = re.sub(
                    r"^```(?:json)?", "", contenido, flags=re.IGNORECASE
                ).strip()
                contenido = re.sub(r"```$", "", contenido).strip()
            return contenido
        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Timeout en validar_contenido_con_ia")
            return None
        except Exception as exc:
            self.logger.exception("Fallo en validar_contenido_con_ia: %s", exc)
            return None

    async def validar_contenido_con_ia(
        self, texto: str, telefono: str
    ) -> Tuple[Optional[str], Optional[str]]:
        if not self.cliente_openai:
            self.logger.warning("⚠️ validar_contenido_con_ia sin cliente OpenAI")
            return None, None

        self.logger.info(
            f"🔍 Validando contenido con IA: '{texto[:50]}...' (phone: {telefono})"
        )

        prompt_sistema = """
Eres un moderador de contenido experto. Detecta si el texto contiene:

1. CONTENIDO ILEGAL O INAPROPIADO:
   - Armas, violencia, delitos
   - Drogas, sustancias ilegales
   - Servicios sexuales, prostitución, contenido pornográfico
   - Odio, discriminación, acoso

2. INPUT SIN SENTIDO O FALSO:
   - "necesito dinero" (cuando NO busca préstamos, es engañoso)
   - "dinero abeja" (sin sentido, alucinación)
   - Textos que no expresan una necesidad real de servicio

Responde SOLO con JSON:
{
  "is_valid": true/false,
  "category": "valid" | "illegal" | "inappropriate" | "nonsense" | "false",
  "reason": "explicación breve",
  "should_ban": true/false
}
"""

        prompt_usuario = f'Analiza este mensaje de usuario: "{texto}"'

        contenido = await self._call_openai(
            prompt_sistema=prompt_sistema, prompt_usuario=prompt_usuario
        )
        if not contenido:
            return None, None

        self.logger.debug(f"🔍 Respuesta validación IA: {contenido}")
        parseado = _safe_json_loads(contenido)
        if not parseado or not isinstance(parseado, dict):
            self.logger.warning(
                f"⚠️ No se pudo parsear respuesta de validación: {contenido}"
            )
            return None, None

        es_valido = parseado.get("is_valid", True)
        categoria = parseado.get("category", "valid")
        razon = parseado.get("reason", "")

        if es_valido and categoria == "valid":
            self.logger.info(f"✅ Contenido válido: '{texto[:30]}...'")
            return None, None

        if categoria in ("nonsense", "false"):
            self.logger.info(
                f"❌ Input sin sentido detectado: '{texto[:30]}...' - {razon}"
            )
            return mensaje_error_input_sin_sentido, None

        conteo_advertencias = await self._get_warning_count(telefono)

        if conteo_advertencias == 0:
            self.logger.warning(
                f"⚠️ Primera ofensa ilegal/inapropiado para {telefono}: {razon}"
            )
            await self._record_warning(telefono, f"{categoria}: {razon}")
            return mensaje_advertencia_contenido_ilegal, None

        self.logger.warning(
            f"🚫 Segunda ofensa ilegal/inapropiado para {telefono}: BANEANDO"
        )
        await self._record_ban(telefono, f"{categoria}: {razon} (2da ofensa)")
        tiempo_reinicio = datetime.utcnow() + timedelta(minutes=15)
        hora_reinicio = tiempo_reinicio.strftime("%H:%M")
        mensaje_ban = mensaje_ban_usuario.format(hora_reinicio=hora_reinicio)
        return None, mensaje_ban
