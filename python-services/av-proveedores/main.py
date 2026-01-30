import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("av-proveedores")

PUERTO_SERVICIO = int(os.getenv("AV_PROVEEDORES_PUERTO", "8005"))

app = FastAPI(
    title="AV Proveedores",
    description="Servicio HTTP para verificación de disponibilidad de proveedores",
    version="0.2.0",
)


class SolicitudDisponibilidad(BaseModel):
    req_id: str
    servicio: str
    ciudad: Optional[str] = None
    candidatos: List[Dict[str, Any]]
    tiempo_espera_segundos: int = 60


class RespuestaDisponibilidad(BaseModel):
    req_id: str
    provider_id: str
    estado: str  # "yes" | "no"


@app.get("/salud")
async def salud():
    """Health check endpoint"""
    return {
        "estado": "ok",
        "servicio": "av-proveedores",
        "puerto": PUERTO_SERVICIO,
        "version": "0.2.0",
    }


@app.post("/check-availability")
async def check_availability(body: SolicitudDisponibilidad):
    """
    Endpoint HTTP para verificar disponibilidad de proveedores.
    Reemplaza el flujo legacy anterior.
    """
    try:
        req_id = body.req_id
        servicio = body.servicio
        ciudad = body.ciudad
        candidatos = body.candidatos
        tiempo_espera = body.tiempo_espera_segundos

        logger.info(
            f"📥 Recibida solicitud HTTP: req_id={req_id}, "
            f"servicio='{servicio}', ciudad={ciudad or 'N/A'}, "
            f"{len(candidatos)} candidatos, timeout={tiempo_espera}s"
        )

        # TODO: Implementar lógica de verificación de disponibilidad
        # Por ahora, simula que nadie responde (comportamiento actual)
        logger.warning(f"⚠️ Disponibilidad no implementada: retorna 0 aceptados")

        return {
            "req_id": req_id,
            "accepted": [],  # Vacío = nadie aceptó
            "responded": [],
            "timeout": False,
            "timestamp": asyncio.get_event_loop().time()
        }

    except Exception as exc:
        logger.error(f"❌ Error en check_availability: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/solicitud")
async def enviar_solicitud(body: SolicitudDisponibilidad):
    """
    Endpoint legacy para compatibilidad.
    Ahora redirige a /check-availability.
    """
    return await check_availability(body)


@app.post("/respuesta")
async def publicar_respuesta(body: RespuestaDisponibilidad):
    """
    Endpoint legacy para compatibilidad.
    Deprecated - Ya no se usa.
    """
    logger.warning(f"⚠️ /respuesta called but deprecated: req_id={body.req_id}")
    return {
        "estado": "deprecated",
        "mensaje": "Este endpoint está deprecated. Use /check-availability en su lugar."
    }


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Iniciando AV Proveedores...")
    logger.info("✅ AV Proveedores listo (modo HTTP puro)")
