from __future__ import annotations

import logging
import os
from typing import Optional

from openai import AsyncOpenAI
from supabase import Client, create_client

from config import configuracion
from infrastructure.embeddings.servicio_embeddings import ServicioEmbeddings

logger = logging.getLogger(__name__)


class DependenciasServicio:
    """Contenedor de dependencias del servicio ai-proveedores.
    Reemplaza los globals de principal.py y los imports dinámicos."""

    def __init__(self) -> None:
        self.supabase: Optional[Client] = None
        self.cliente_openai: Optional[AsyncOpenAI] = None
        self.servicio_embeddings: Optional[ServicioEmbeddings] = None

    def inicializar(self) -> None:
        url = configuracion.supabase_url or os.getenv("SUPABASE_URL", "")
        clave = configuracion.supabase_service_key
        clave_openai = os.getenv("OPENAI_API_KEY", "")

        if url and clave:
            self.supabase = create_client(url, clave)
            from infrastructure.database import set_supabase_client
            set_supabase_client(self.supabase)
            logger.info("✅ Conectado a Supabase (via dependencies)")
        else:
            logger.warning("⚠️ No se configuró Supabase")

        if clave_openai:
            self.cliente_openai = AsyncOpenAI(api_key=clave_openai)
            self.servicio_embeddings = ServicioEmbeddings(
                cliente_openai=self.cliente_openai,
                modelo=configuracion.modelo_embeddings,
                cache_ttl=configuracion.ttl_cache_embeddings,
                timeout=configuracion.tiempo_espera_embeddings,
            )
            logger.info("✅ OpenAI + Embeddings inicializados (via dependencies)")
        else:
            logger.warning("⚠️ No se configuró OpenAI")


# Instancia única del contenedor — se inicializa en startup
deps = DependenciasServicio()
