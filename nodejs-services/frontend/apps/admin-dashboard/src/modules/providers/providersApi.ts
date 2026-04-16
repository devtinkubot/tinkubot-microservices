import {
  apiProveedores,
  type ProviderActionResponse,
  type ProviderOnboardingResetResponse,
  type ProviderProfessionalProfileUpdatePayload,
  type ProviderProfessionalProfileUpdateResponse,
  type ProviderRecord,
  type ProviderServiceReviewActionPayload,
  type ProviderServiceReviewActionResponse,
} from "@tinkubot/api-client";
import type { AccionProveedorOpciones, ProviderBucket } from "./providersTypes";

export async function obtenerProveedoresPorBucket(
  bucket: ProviderBucket,
): Promise<ProviderRecord[]> {
  switch (bucket) {
    case "onboarding":
      return apiProveedores.obtenerProveedoresOnboarding();
    case "new":
      return apiProveedores.obtenerProveedoresNuevos();
    case "operativos":
      return apiProveedores.obtenerProveedoresOperativos();
    case "profile_incomplete":
      return apiProveedores.obtenerProveedoresPerfilProfesionalIncompleto();
    default:
      return [];
  }
}

export async function obtenerDetalleProveedor(
  id: string,
): Promise<ProviderRecord> {
  return apiProveedores.obtenerDetalleProveedor(id);
}

export async function actualizarPerfilProfesional(
  id: string,
  payload: ProviderProfessionalProfileUpdatePayload,
): Promise<ProviderProfessionalProfileUpdateResponse> {
  return apiProveedores.actualizarPerfilProfesional(id, payload);
}

export async function ejecutarAccionProveedor(
  id: string,
  accion: "review" | "reset",
  opciones: AccionProveedorOpciones = {},
): Promise<ProviderActionResponse | ProviderOnboardingResetResponse> {
  if (accion === "reset" || opciones.status === "rejected") {
    return apiProveedores.resetearProveedorOnboarding(id);
  }
  return apiProveedores.revisarProveedor(id, opciones);
}

export async function aprobarReviewServicio(
  reviewId: string,
  payload: ProviderServiceReviewActionPayload,
): Promise<ProviderServiceReviewActionResponse> {
  return apiProveedores.aprobarReviewServicioCatalogo(reviewId, payload);
}

export async function rechazarReviewServicio(
  reviewId: string,
  payload: { reviewer?: string } = {},
): Promise<ProviderServiceReviewActionResponse> {
  return apiProveedores.rechazarReviewServicioCatalogo(reviewId, payload);
}
