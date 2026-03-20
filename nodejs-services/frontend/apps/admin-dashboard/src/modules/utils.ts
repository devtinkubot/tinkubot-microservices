const ECUADOR_TIME_ZONE = "America/Guayaquil";

const FORMATO_HORA_ECUADOR = new Intl.DateTimeFormat("es-EC", {
  dateStyle: "short",
  timeStyle: "short",
  timeZone: ECUADOR_TIME_ZONE,
});

const API_URL_BASE = "";

const FECHA_SOLO_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const FECHA_HORA_SIN_ZONA_REGEX =
  /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/;
const FECHA_CON_ZONA_REGEX = /(Z|[+-]\d{2}:?\d{2})$/i;

export function parsearMarcaTemporalSupabase(
  value?: string | Date | null,
): Date | null {
  if (!value) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  const raw = value.trim();
  if (!raw) return null;

  let candidate = raw;
  if (FECHA_SOLO_REGEX.test(candidate)) {
    candidate = `${candidate}T00:00:00`;
  } else if (
    FECHA_HORA_SIN_ZONA_REGEX.test(candidate) &&
    !FECHA_CON_ZONA_REGEX.test(candidate)
  ) {
    candidate = candidate.replace(" ", "T");
    candidate += "Z";
  }

  const parsed = new Date(candidate);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatearMarcaTemporalEcuador(
  value?: string | Date | null,
): string {
  const parsed = parsearMarcaTemporalSupabase(value);
  if (!parsed) return "—";
  return FORMATO_HORA_ECUADOR.format(parsed);
}

export const Utils = {
  obtenerUrlBaseApi: () => API_URL_BASE,
  formatearMarcaDeTiempo: () => FORMATO_HORA_ECUADOR.format(new Date()),
  formatearMarcaTemporalEcuador,
  parsearMarcaTemporalSupabase,
  alternarSpinner: (mostrar: boolean) => {
    const spinner = document.querySelector<HTMLDivElement>(
      ".refresh-btn .loading-spinner",
    );
    if (spinner) {
      spinner.style.display = mostrar ? "inline-block" : "none";
    }
  },
};

export type UtilsModule = typeof Utils;
