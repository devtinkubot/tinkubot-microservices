import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

from asyncio_mqtt import Client, MqttError
from fastapi import BackgroundTasks, FastAPI, HTTPException
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
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_PUBLISH_TIMEOUT = float(os.getenv("MQTT_PUBLISH_TIMEOUT", "5"))
LOG_SAMPLING_RATE = int(os.getenv("LOG_SAMPLING_RATE", "10"))

_publish_queue: "asyncio.Queue[tuple[str, Dict[str, Any]]]" = asyncio.Queue()
_mqtt_client: Optional[Client] = None
_mqtt_lock = asyncio.Lock()

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


async def _ensure_client() -> Client:
    global _mqtt_client
    if _mqtt_client and not _mqtt_client._client.is_connected():
        _mqtt_client = None

    if _mqtt_client is None:
        async with _mqtt_lock:
            if _mqtt_client is None:
                _mqtt_client = Client(**parametros_mqtt())
                await _mqtt_client.connect()
                logger.info("✅ Cliente MQTT conectado (%s:%s)", MQTT_HOST, MQTT_PORT)
    return _mqtt_client


async def _publisher_loop():
    """Bucle de publicación que reutiliza una conexión MQTT persistente."""
    while True:
        tema, cuerpo = await _publish_queue.get()
        try:
            client = await _ensure_client()
            payload = json.dumps(cuerpo).encode("utf-8")
            await asyncio.wait_for(
                client.publish(tema, payload, qos=MQTT_QOS),
                timeout=MQTT_PUBLISH_TIMEOUT,
            )
            if hash(cuerpo.get("req_id", "")) % LOG_SAMPLING_RATE == 0:
                logger.info("📤 MQTT publicado", extra={"tema": tema, "req_id": cuerpo.get("req_id")})
        except Exception as exc:
            logger.error("❌ Error publicando en MQTT: %s", exc)
            # Devolver al final de la cola para reintentar de forma simple
            await asyncio.sleep(0.5)
            await _publish_queue.put((tema, cuerpo))
        finally:
            _publish_queue.task_done()


async def publicar_mqtt(tema: str, cuerpo: Dict[str, Any]) -> None:
    """Encola publicación para ser procesada por el publisher loop."""
    await _publish_queue.put((tema, cuerpo))


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
async def enviar_solicitud(body: SolicitudDisponibilidad, background_tasks: BackgroundTasks):
    try:
        if len(body.candidatos) > 200:
            raise HTTPException(status_code=400, detail="Demasiados candidatos en la solicitud")
        payload = body.dict()
        background_tasks.add_task(publicar_mqtt, MQTT_TEMA_PETICION, payload)
        return {"estado": "enviado", "req_id": body.req_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/respuesta")
async def publicar_respuesta(body: RespuestaDisponibilidad, background_tasks: BackgroundTasks):
    try:
        payload = body.dict()
        background_tasks.add_task(publicar_mqtt, MQTT_TEMA_RESPUESTA, payload)
        return {
            "estado": "enviado",
            "req_id": body.req_id,
            "provider_id": body.provider_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.on_event("startup")
async def probar_conexion_mqtt():
    try:
        await _ensure_client()
        asyncio.create_task(_publisher_loop())
        logger.info("✅ Broker MQTT accesible y publisher loop iniciado")
    except Exception as exc:
        logger.warning("⚠️ Broker MQTT no accesible en arranque: %s", exc)
