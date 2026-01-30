import { realizarSolicitudHttp } from './http';
import type { WhatsAppStatusResponse } from './types';

const ENDPOINT_ESTADO = '/api/accounts';
const ENDPOINT_REGENERAR = (instanciaId: string) => `/api/accounts/${instanciaId}/login`;

interface RespuestaRegeneracion {
  message?: string;
}

export async function obtenerEstadoWhatsApp(): Promise<WhatsAppStatusResponse> {
  const accounts = await realizarSolicitudHttp<any[]>(ENDPOINT_ESTADO);

  // Convertir formato de wa-gateway al formato esperado por el frontend
  const statusMap: WhatsAppStatusResponse = {};
  accounts.forEach(account => {
    statusMap[account.account_id] = {
      connected: account.connection_status === 'connected',
      qr: account.qr_code || null,
      phone: account.phone_number || null,
      battery: null
    };
  });

  return statusMap;
}

export async function regenerarInstanciaWhatsApp(
  instanciaId: string
): Promise<RespuestaRegeneracion> {
  return realizarSolicitudHttp<RespuestaRegeneracion>(ENDPOINT_REGENERAR(instanciaId), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ force: true })
  });
}
