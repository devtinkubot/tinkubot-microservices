import { realizarSolicitudHttp } from './http';
import type {
  MonetizationOverview,
  MonetizationProviderRecord,
  MonetizationProvidersResponse,
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

export async function obtenerMonetizacionResumen(): Promise<MonetizationOverview> {
  return realizarSolicitudHttp<MonetizationOverview>(`${RUTA_BASE}/monetization/overview`);
}

export async function obtenerMonetizacionProveedores(params?: {
  status?: 'all' | 'active' | 'paused_paywall' | 'suspended';
  limit?: number;
  offset?: number;
}): Promise<MonetizationProvidersResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (typeof params?.limit === 'number') query.set('limit', String(params.limit));
  if (typeof params?.offset === 'number') query.set('offset', String(params.offset));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return realizarSolicitudHttp<MonetizationProvidersResponse>(
    `${RUTA_BASE}/monetization/providers${suffix}`
  );
}

export async function obtenerMonetizacionProveedor(
  providerId: string
): Promise<MonetizationProviderRecord> {
  return realizarSolicitudHttp<MonetizationProviderRecord>(
    `${RUTA_BASE}/monetization/provider/${providerId}`
  );
}
