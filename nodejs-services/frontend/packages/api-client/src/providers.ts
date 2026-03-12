import { realizarSolicitudHttp } from './http';
import type {
  MonetizationOverview,
  MonetizationProviderRecord,
  MonetizationProvidersResponse,
  ProviderActionPayload,
  ProviderActionResponse,
  ProviderRecord,
  TaxonomyDraftApplyResponse,
  TaxonomyDraftsResponse,
  TaxonomyOverviewResponse,
  TaxonomyPublishResponse,
  TaxonomySuggestionClustersResponse,
  TaxonomySuggestionApprovePayload,
  TaxonomySuggestionApproveResponse,
  TaxonomySuggestionReviewPayload,
  TaxonomySuggestionReviewResponse,
  TaxonomySuggestionsResponse
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

export async function obtenerTaxonomiaSugerencias(params?: {
  status?: 'all' | 'pending' | 'enriched' | 'approved' | 'rejected' | 'superseded';
  limit?: number;
}): Promise<TaxonomySuggestionsResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (typeof params?.limit === 'number') query.set('limit', String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return realizarSolicitudHttp<TaxonomySuggestionsResponse>(
    `${RUTA_BASE}/taxonomy/suggestions${suffix}`
  );
}

export async function obtenerTaxonomiaClusters(params?: {
  status?: 'all' | 'pending' | 'enriched' | 'approved' | 'rejected' | 'superseded';
  limit?: number;
}): Promise<TaxonomySuggestionClustersResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (typeof params?.limit === 'number') query.set('limit', String(params.limit));
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return realizarSolicitudHttp<TaxonomySuggestionClustersResponse>(
    `${RUTA_BASE}/taxonomy/suggestion-clusters${suffix}`
  );
}

export async function obtenerTaxonomiaOverview(): Promise<TaxonomyOverviewResponse> {
  return realizarSolicitudHttp<TaxonomyOverviewResponse>(`${RUTA_BASE}/taxonomy/overview`);
}

export async function revisarTaxonomiaSugerencia(
  suggestionId: string,
  payload: TaxonomySuggestionReviewPayload
): Promise<TaxonomySuggestionReviewResponse> {
  return realizarSolicitudHttp<TaxonomySuggestionReviewResponse>(
    `${RUTA_BASE}/taxonomy/suggestions/${suggestionId}/review`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }
  );
}

export async function revisarTaxonomiaCluster(
  clusterId: string,
  payload: TaxonomySuggestionReviewPayload
): Promise<TaxonomySuggestionReviewResponse> {
  return realizarSolicitudHttp<TaxonomySuggestionReviewResponse>(
    `${RUTA_BASE}/taxonomy/suggestion-clusters/${encodeURIComponent(clusterId)}/review`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }
  );
}

export async function aprobarTaxonomiaSugerencia(
  suggestionId: string,
  payload: TaxonomySuggestionApprovePayload = {}
): Promise<TaxonomySuggestionApproveResponse> {
  return realizarSolicitudHttp<TaxonomySuggestionApproveResponse>(
    `${RUTA_BASE}/taxonomy/suggestions/${suggestionId}/approve-draft`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }
  );
}

export async function aprobarTaxonomiaCluster(
  clusterId: string,
  payload: TaxonomySuggestionApprovePayload = {}
): Promise<TaxonomySuggestionApproveResponse> {
  return realizarSolicitudHttp<TaxonomySuggestionApproveResponse>(
    `${RUTA_BASE}/taxonomy/suggestion-clusters/${encodeURIComponent(clusterId)}/approve-draft`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }
  );
}

export async function obtenerTaxonomiaDrafts(): Promise<TaxonomyDraftsResponse> {
  return realizarSolicitudHttp<TaxonomyDraftsResponse>(`${RUTA_BASE}/taxonomy/drafts`);
}

export async function aplicarTaxonomiaDraft(
  changeId: string
): Promise<TaxonomyDraftApplyResponse> {
  return realizarSolicitudHttp<TaxonomyDraftApplyResponse>(
    `${RUTA_BASE}/taxonomy/drafts/${changeId}/apply`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    }
  );
}

export async function publicarTaxonomiaDrafts(): Promise<TaxonomyPublishResponse> {
  return realizarSolicitudHttp<TaxonomyPublishResponse>(`${RUTA_BASE}/taxonomy/publish`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    }
  });
}
