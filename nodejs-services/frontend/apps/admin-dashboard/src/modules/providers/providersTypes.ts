import type {
  ProviderRecord,
  ProviderServiceReview,
} from "@tinkubot/api-client";

export type ProviderBucket =
  | "onboarding"
  | "new"
  | "operativos"
  | "profile_incomplete";

export type OnboardingColumn = {
  state: string;
  title: string;
};

export type OnboardingAgeLevel = "fresh" | "warning" | "critical";

export interface EstadoProveedores {
  proveedores: ProviderRecord[];
  estaCargando: boolean;
  idAccionEnProceso: string | null;
  idReviewEnProceso: string | null;
  proveedorSeleccionado: ProviderRecord | null;
  reviewSeleccionada: ProviderServiceReview | null;
  bucketActivo: ProviderBucket;
}

export interface AccionProveedorOpciones {
  status?: ProviderRecord["status"];
  reviewer?: string;
  phone?: string;
  message?: string;
  documentFirstNames?: string;
  documentLastNames?: string;
  documentIdNumber?: string;
}

export type ResultadoRevisionOpcion = {
  value: ProviderRecord["status"];
  label: string;
};

export type ModalInstance = {
  show: () => void;
  hide: () => void;
};
