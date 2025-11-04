import { realizarSolicitudHttp } from './http';
import type { WhatsAppStatusResponse } from './types';

const ENDPOINT_ESTADO = '/whatsapp-status';
const ENDPOINT_REGENERAR = (instanciaId: string) => `/api/whatsapp/${instanciaId}/refresh`;

interface RespuestaRegeneracion {
  message?: string;
}

export async function obtenerEstadoWhatsApp(): Promise<WhatsAppStatusResponse> {
  return realizarSolicitudHttp<WhatsAppStatusResponse>(ENDPOINT_ESTADO);
}

export async function regenerarInstanciaWhatsApp(
  instanciaId: string
): Promise<RespuestaRegeneracion> {
  return realizarSolicitudHttp<RespuestaRegeneracion>(ENDPOINT_REGENERAR(instanciaId), {
    method: 'POST'
  });
}
