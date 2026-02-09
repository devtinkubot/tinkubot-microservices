import { realizarSolicitudHttp } from './http';
import type {
  ProviderActionPayload,
  ProviderActionResponse,
  ProviderRecord
} from './types';

const RUTA_BASE = '/admin/providers';

interface RespuestaProveedoresPendientes {
  providers: ProviderRecord[];
}

export async function obtenerProveedoresPendientes(): Promise<ProviderRecord[]> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(`${RUTA_BASE}/pending`);
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function obtenerProveedoresNuevos(): Promise<ProviderRecord[]> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(`${RUTA_BASE}/new`);
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function obtenerProveedoresPostRevision(): Promise<ProviderRecord[]> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(
    `${RUTA_BASE}/post-review`
  );
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function aprobarProveedor(
  proveedorId: string,
  carga: ProviderActionPayload = {}
): Promise<ProviderActionResponse> {
  return realizarSolicitudHttp<ProviderActionResponse>(`${RUTA_BASE}/${proveedorId}/approve`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(carga)
  });
}

export async function rechazarProveedor(
  proveedorId: string,
  carga: ProviderActionPayload = {}
): Promise<ProviderActionResponse> {
  return realizarSolicitudHttp<ProviderActionResponse>(`${RUTA_BASE}/${proveedorId}/reject`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(carga)
  });
}

export async function revisarProveedor(
  proveedorId: string,
  carga: ProviderActionPayload = {}
): Promise<ProviderActionResponse> {
  return realizarSolicitudHttp<ProviderActionResponse>(`${RUTA_BASE}/${proveedorId}/review`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(carga)
  });
}
