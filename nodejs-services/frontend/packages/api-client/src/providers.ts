import { realizarSolicitudHttp } from "./http";
import type {
  MonetizationOverview,
  MonetizationProviderRecord,
  MonetizationProvidersResponse,
  ProviderActionPayload,
  ProviderActionResponse,
  ProviderOnboardingResetResponse,
  ProviderRecord,
  ProviderServiceReviewActionPayload,
  ProviderServiceReviewActionResponse,
  ProviderStatusOverviewResponse,
  ProviderProfessionalProfileUpdatePayload,
  ProviderProfessionalProfileUpdateResponse,
} from "./types";

const RUTA_BASE = "/admin/providers";

interface RespuestaProveedoresPendientes {
  providers: ProviderRecord[];
}

interface RespuestaDetalleProveedor {
  provider: ProviderRecord;
}

export async function obtenerProveedoresPendientes(): Promise<
  ProviderRecord[]
> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(
    `${RUTA_BASE}/pending`,
  );
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function obtenerProveedoresNuevos(): Promise<ProviderRecord[]> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(
    `${RUTA_BASE}/new`,
  );
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function obtenerProveedoresOnboarding(): Promise<
  ProviderRecord[]
> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(
    `${RUTA_BASE}/onboarding`,
  );
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function obtenerProveedoresOperativos(): Promise<
  ProviderRecord[]
> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(
    `${RUTA_BASE}/operativos`,
  );
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function obtenerProveedoresPostRevision(): Promise<
  ProviderRecord[]
> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(
    `${RUTA_BASE}/post-review`,
  );
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function obtenerProveedoresPerfilProfesionalIncompleto(): Promise<
  ProviderRecord[]
> {
  const datos = await realizarSolicitudHttp<RespuestaProveedoresPendientes>(
    `${RUTA_BASE}/profile-incomplete`,
  );
  if (Array.isArray(datos.providers)) {
    return datos.providers;
  }
  return [];
}

export async function obtenerDetalleProveedor(
  proveedorId: string,
): Promise<ProviderRecord> {
  const datos = await realizarSolicitudHttp<RespuestaDetalleProveedor>(
    `${RUTA_BASE}/${proveedorId}`,
  );
  return datos.provider;
}

export async function aprobarProveedor(
  proveedorId: string,
  carga: ProviderActionPayload = {},
): Promise<ProviderActionResponse> {
  return realizarSolicitudHttp<ProviderActionResponse>(
    `${RUTA_BASE}/${proveedorId}/approve`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(carga),
    },
  );
}

export async function rechazarProveedor(
  proveedorId: string,
  carga: ProviderActionPayload = {},
): Promise<ProviderActionResponse> {
  return realizarSolicitudHttp<ProviderActionResponse>(
    `${RUTA_BASE}/${proveedorId}/reject`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(carga),
    },
  );
}

export async function revisarProveedor(
  proveedorId: string,
  carga: ProviderActionPayload = {},
): Promise<ProviderActionResponse> {
  return realizarSolicitudHttp<ProviderActionResponse>(
    `${RUTA_BASE}/${proveedorId}/review`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(carga),
    },
  );
}

export async function actualizarPerfilProfesional(
  proveedorId: string,
  carga: ProviderProfessionalProfileUpdatePayload,
): Promise<ProviderProfessionalProfileUpdateResponse> {
  return realizarSolicitudHttp<ProviderProfessionalProfileUpdateResponse>(
    `${RUTA_BASE}/${proveedorId}/professional-profile`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(carga),
    },
  );
}

export async function aprobarReviewServicioCatalogo(
  reviewId: string,
  carga: ProviderServiceReviewActionPayload,
): Promise<ProviderServiceReviewActionResponse> {
  return realizarSolicitudHttp<ProviderServiceReviewActionResponse>(
    `${RUTA_BASE}/service-reviews/${reviewId}/approve`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(carga),
    },
  );
}

export async function rechazarReviewServicioCatalogo(
  reviewId: string,
  carga: {
    reviewer?: string;
  } = {},
): Promise<ProviderServiceReviewActionResponse> {
  return realizarSolicitudHttp<ProviderServiceReviewActionResponse>(
    `${RUTA_BASE}/service-reviews/${reviewId}/reject`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(carga),
    },
  );
}

export async function resetearProveedorOnboarding(
  proveedorId: string,
): Promise<ProviderOnboardingResetResponse> {
  return realizarSolicitudHttp<ProviderOnboardingResetResponse>(
    `${RUTA_BASE}/${proveedorId}/reset`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ provider_id: proveedorId }),
    },
  );
}

export async function obtenerResumenEstadosProveedores(): Promise<ProviderStatusOverviewResponse> {
  return realizarSolicitudHttp<ProviderStatusOverviewResponse>(
    `${RUTA_BASE}/summary`,
  );
}

export async function obtenerMonetizacionResumen(params?: {
  status?: "all" | "active" | "paused_paywall";
}): Promise<MonetizationOverview> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return realizarSolicitudHttp<MonetizationOverview>(
    `${RUTA_BASE}/monetization/overview${suffix}`,
  );
}

export async function obtenerMonetizacionProveedores(params?: {
  status?: "all" | "active" | "paused_paywall";
  limit?: number;
  offset?: number;
}): Promise<MonetizationProvidersResponse> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (typeof params?.limit === "number")
    query.set("limit", String(params.limit));
  if (typeof params?.offset === "number")
    query.set("offset", String(params.offset));
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return realizarSolicitudHttp<MonetizationProvidersResponse>(
    `${RUTA_BASE}/monetization/providers${suffix}`,
  );
}

export async function obtenerMonetizacionProveedor(
  providerId: string,
): Promise<MonetizationProviderRecord> {
  return realizarSolicitudHttp<MonetizationProviderRecord>(
    `${RUTA_BASE}/monetization/provider/${providerId}`,
  );
}
