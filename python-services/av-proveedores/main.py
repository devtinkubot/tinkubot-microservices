import json
import logging
import os
from typing import Any, Dict, Optional

from asyncio_mqtt import Client, MqttError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("av-proveedores")

# Configuración de MQTT y puerto del servicio
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USUARIO = os.getenv("MQTT_USUARIO")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_TEMA_PETICION = os.getenv("MQTT_TEMA_PETICION", "av-proveedores/solicitud")
MQTT_TEMA_RESPUESTA = os.getenv("MQTT_TEMA_RESPUESTA", "av-proveedores/respuesta")
PUERTO_SERVICIO = int(os.getenv("AV_PROVEEDORES_PUERTO", "8005"))

app = FastAPI(
    title="AV Proveedores",
    description="Puente MQTT para pruebas de disponibilidad de proveedores (aislado, sin integración).",
    version="0.1.0",
)


class SolicitudDisponibilidad(BaseModel):
    req_id: str
    servicio: str
    ciudad: Optional[str] = None
    candidatos: list[Dict[str, Any]]
    tiempo_espera_segundos: int = 60


class RespuestaDisponibilidad(BaseModel):
    req_id: str
    provider_id: str
    estado: str  # "yes" | "no"


def parametros_mqtt() -> Dict[str, Any]:
    parametros: Dict[str, Any] = {"hostname": MQTT_HOST, "port": MQTT_PORT}
    if MQTT_USUARIO and MQTT_PASSWORD:
        parametros.update({"username": MQTT_USUARIO, "password": MQTT_PASSWORD})
    return parametros


async def publicar_mqtt(tema: str, cuerpo: Dict[str, Any]) -> None:
    try:
        async with Client(**parametros_mqtt()) as cliente:
            await cliente.publish(tema, json.dumps(cuerpo).encode("utf-8"))
            logger.info("📤 MQTT publicado en %s -> %s", tema, cuerpo.get("req_id"))
    except MqttError as exc:
        logger.error("❌ No se pudo publicar en MQTT: %s", exc)
        raise


@app.get("/salud")
async def salud():
    return {
        "estado": "ok",
        "mqtt_host": MQTT_HOST,
        "mqtt_port": MQTT_PORT,
        "tema_peticiones": MQTT_TEMA_PETICION,
        "tema_respuestas": MQTT_TEMA_RESPUESTA,
        "puerto": PUERTO_SERVICIO,
    }


@app.post("/solicitud")
async def enviar_solicitud(body: SolicitudDisponibilidad):
    try:
        await publicar_mqtt(MQTT_TEMA_PETICION, body.dict())
        return {"estado": "publicado", "req_id": body.req_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/respuesta")
async def publicar_respuesta(body: RespuestaDisponibilidad):
    try:
        await publicar_mqtt(MQTT_TEMA_RESPUESTA, body.dict())
        return {
            "estado": "publicado",
            "req_id": body.req_id,
            "provider_id": body.provider_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.on_event("startup")
async def probar_conexion_mqtt():
    try:
        async with Client(**parametros_mqtt()) as cliente:
            await cliente.publish("av-proveedores/salud", b"ok")
            logger.info("✅ Broker MQTT accesible (%s:%s)", MQTT_HOST, MQTT_PORT)
    except Exception as exc:
        logger.warning("⚠️ Broker MQTT no accesible en arranque: %s", exc)
