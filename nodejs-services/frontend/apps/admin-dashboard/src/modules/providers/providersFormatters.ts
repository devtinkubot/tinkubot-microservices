import {
  formatearMarcaTemporalEcuador,
  formatearTelefonoEcuador,
  parsearMarcaTemporalSupabase,
} from "../utils";
import type { ProviderRecord } from "@tinkubot/api-client";
import type {
  OnboardingAgeLevel,
  OnboardingColumn,
  ProviderBucket,
} from "./providersTypes";

const ONBOARDING_COLUMNS: OnboardingColumn[] = [
  { state: "onboarding_city", title: "Ciudad" },
  { state: "onboarding_dni_front_photo", title: "Cédula frontal" },
  { state: "onboarding_face_photo", title: "Foto de perfil" },
  { state: "onboarding_experience", title: "Experiencia" },
  { state: "onboarding_real_phone", title: "Teléfono real" },
  { state: "onboarding_specialty", title: "Servicios" },
];

const formateadorFecha = new Intl.DateTimeFormat("es-EC", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Guayaquil",
});

export const limpiarTelefono = (
  valor: string | null | undefined,
): string | null => {
  if (!valor) return null;
  const limpio = valor.replace(/[^\d+]/g, "");
  return limpio.length > 0 ? limpio : null;
};

export const limpiarTelefonoWhatsApp = (
  valor: string | null | undefined,
): string | null => {
  const telefono = limpiarTelefono(valor);
  if (!telefono) return null;
  const digitos = telefono.replace(/[^\d]/g, "");
  return digitos.length > 0 ? digitos : null;
};

export const extraerPrimerNombre = (
  nombreCompleto: string | null | undefined,
): string => {
  const texto = nombreCompleto?.trim();
  if (!texto) return "Proveedor";
  return texto.split(/\s+/).filter(Boolean)[0] || "Proveedor";
};

export const normalizarClaveServicio = (
  valor: string | null | undefined,
): string | null => {
  const texto = valor?.trim();
  if (!texto) return null;
  return texto.toLowerCase().replace(/\s+/g, " ");
};

export const esIdentificadorWhatsAppCrudo = (valor: string): boolean => {
  const texto = valor.trim();
  if (!texto) return false;
  if (texto.includes("@s.whatsapp.net") || texto.includes("@lid")) {
    return true;
  }
  return /^\d{8,}$/.test(texto.replace(/[^\d]/g, ""));
};

export const resolverTextoVisible = (
  valor: string | null | undefined,
): string | null => {
  const texto = valor?.trim();
  if (!texto) return null;
  return esIdentificadorWhatsAppCrudo(texto)
    ? formatearTelefonoEcuador(texto)
    : texto;
};

export const resolverNombreVisibleProveedor = (proveedor: ProviderRecord): string => {
  const displayName = proveedor.displayName?.trim();
  const formattedName = proveedor.formattedName?.trim();
  const nombreDocumento = [
    proveedor.documentFirstNames?.trim(),
    proveedor.documentLastNames?.trim(),
  ]
    .filter(Boolean)
    .join(" ")
    .trim();

  return displayName || formattedName || nombreDocumento || "Proveedor";
};

export const resolverNombreVisibleOperativoProveedor = (
  proveedor: ProviderRecord,
): string => {
  const nombreDocumento = [
    proveedor.documentFirstNames?.trim(),
    proveedor.documentLastNames?.trim(),
  ]
    .filter(Boolean)
    .join(" ")
    .trim();

  return (
    nombreDocumento ||
    proveedor.formattedName?.trim() ||
    proveedor.displayName?.trim() ||
    "Proveedor"
  );
};

export const resolverNombreVisibleSegunBucketActivo = (
  proveedor: ProviderRecord,
  bucketActivo: ProviderBucket,
): string => {
  return bucketActivo === "operativos"
    ? resolverNombreVisibleOperativoProveedor(proveedor)
    : resolverNombreVisibleProveedor(proveedor);
};

export const resolverTelefonoVisibleOperativoProveedor = (
  proveedor: ProviderRecord,
): string | null => {
  return (
    resolverTextoVisible(proveedor.contactPhone) ??
    resolverTextoVisible(proveedor.realPhone) ??
    resolverTextoVisible(proveedor.phone)
  );
};

export const normalizarPasoOnboarding = (
  proveedor: ProviderRecord,
): string | null => {
  const estado = proveedor.onboardingStep?.trim();
  if (!estado) {
    return null;
  }

  return ONBOARDING_COLUMNS.some((column) => column.state === estado)
    ? estado
    : null;
};

export const normalizarListaServiciosEditable = (
  servicios: Array<string | null | undefined> | undefined,
): string[] => {
  return (servicios || [])
    .map((servicio) => servicio?.trim() || "")
    .filter((servicio) => servicio.length > 0);
};

export const construirUrlWhatsApp = (
  telefono: string | null | undefined,
): string | null => {
  const digitos = limpiarTelefonoWhatsApp(telefono);
  if (!digitos) return null;
  return `https://wa.me/${digitos}`;
};

export const normalizarTelefonoCopiable = (
  telefono: string | null | undefined,
): string | null => {
  const digitos = limpiarTelefonoWhatsApp(telefono);
  if (!digitos) return null;
  return `+${digitos}`;
};

export const formatearAntiguedadAprobacion = (
  timestamp: string | null | undefined,
): string | null => {
  if (!timestamp) return null;
  const fecha = parsearMarcaTemporalSupabase(timestamp);
  if (!fecha) return null;
  const diffMs = Date.now() - fecha.getTime();
  if (!Number.isFinite(diffMs) || diffMs < 0) return null;

  const diffHoras = Math.floor(diffMs / (60 * 60 * 1000));
  if (diffHoras < 1) {
    return "Hace menos de 1 hora";
  }

  if (diffHoras < 24) {
    return `Hace ${diffHoras} ${diffHoras === 1 ? "hora" : "horas"}`;
  }

  const diffDias = Math.floor(diffHoras / 24);
  return `Hace ${diffDias} ${diffDias === 1 ? "día" : "días"}`;
};

export const resolverAntiguedadOnboarding = (
  timestamp: string | null | undefined,
): {
  horas: number | null;
  etiqueta: string | null;
  nivel: OnboardingAgeLevel;
} => {
  if (!timestamp) {
    return { horas: null, etiqueta: null, nivel: "fresh" };
  }

  const fecha = parsearMarcaTemporalSupabase(timestamp);
  if (!fecha) {
    return { horas: null, etiqueta: null, nivel: "fresh" };
  }

  const diffMs = Date.now() - fecha.getTime();
  if (!Number.isFinite(diffMs) || diffMs < 0) {
    return { horas: null, etiqueta: null, nivel: "fresh" };
  }

  const horas = Math.floor(diffMs / (60 * 60 * 1000));
  const dias = Math.floor(horas / 24);
  const etiqueta =
    horas < 1
      ? "Hace menos de 1 hora"
      : horas < 24
        ? `Hace ${horas} ${horas === 1 ? "hora" : "horas"}`
        : `Hace ${dias} ${dias === 1 ? "día" : "días"}`;
  const nivel: OnboardingAgeLevel =
    horas >= 72 ? "critical" : horas >= 48 ? "warning" : "fresh";

  return { horas, etiqueta, nivel };
};

export const formatearFechaLarga = (valor?: string | null): string => {
  if (!valor) return "—";
  const formateado = formatearMarcaTemporalEcuador(valor);
  if (formateado !== "—") return formateado;
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) return valor;
  return formateadorFecha.format(fecha);
};

export const escaparHtml = (texto: string): string => {
  return texto.replace(/[&<>"']/g, (caracter) => {
    const mapa: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return mapa[caracter] ?? caracter;
  });
};
