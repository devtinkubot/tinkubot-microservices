import type { ProviderRecord, ProviderServiceReview } from "@tinkubot/api-client";
import type { EstadoProveedores, ProviderBucket } from "./providersTypes";

const estado: EstadoProveedores = {
  proveedores: [],
  estaCargando: false,
  idAccionEnProceso: null,
  idReviewEnProceso: null,
  proveedorSeleccionado: null,
  reviewSeleccionada: null,
  bucketActivo: "onboarding",
};

export const obtenerProveedores = (): readonly ProviderRecord[] =>
  estado.proveedores;

export const obtenerEstaCargando = (): boolean => estado.estaCargando;

export const obtenerIdAccionEnProceso = (): string | null =>
  estado.idAccionEnProceso;

export const obtenerIdReviewEnProceso = (): string | null =>
  estado.idReviewEnProceso;

export const obtenerProveedorSeleccionado = (): ProviderRecord | null =>
  estado.proveedorSeleccionado;

export const obtenerReviewSeleccionada = (): ProviderServiceReview | null =>
  estado.reviewSeleccionada;

export const obtenerBucketActivo = (): ProviderBucket => estado.bucketActivo;

export const establecerProveedores = (proveedores: ProviderRecord[]): void => {
  estado.proveedores = proveedores;
};

export const establecerEstadoCarga = (estaCargando: boolean): void => {
  estado.estaCargando = estaCargando;
};

export const establecerIdAccionEnProceso = (id: string | null): void => {
  estado.idAccionEnProceso = id;
};

export const establecerIdReviewEnProceso = (id: string | null): void => {
  estado.idReviewEnProceso = id;
};

export const establecerProveedorSeleccionado = (
  proveedor: ProviderRecord | null,
): void => {
  estado.proveedorSeleccionado = proveedor;
};

export const establecerReviewSeleccionada = (
  review: ProviderServiceReview | null,
): void => {
  estado.reviewSeleccionada = review;
};

export const establecerBucketActivo = (bucket: ProviderBucket): void => {
  estado.bucketActivo = bucket;
};
