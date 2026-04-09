import {
  apiProveedores,
  type MonetizationOverview,
  type MonetizationProviderRecord,
} from "@tinkubot/api-client";
import { formatearMarcaTemporalEcuador, formatearTelefonoEcuador } from "./utils";

type BillingFilter = "all" | "active" | "paused_paywall";

interface MonetizationState {
  loading: boolean;
  filter: BillingFilter;
  overview: MonetizationOverview | null;
  providers: MonetizationProviderRecord[];
}

const state: MonetizationState = {
  loading: false,
  filter: "all",
  overview: null,
  providers: [],
};

const formatter = new Intl.DateTimeFormat("es-EC", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Guayaquil",
});

function getElement<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

function setLoading(loading: boolean) {
  state.loading = loading;
  const loadingBlock = getElement<HTMLDivElement>("#monetization-loading");
  const tableWrapper = getElement<HTMLDivElement>(
    "#monetization-table-wrapper",
  );
  const emptyBlock = getElement<HTMLDivElement>("#monetization-empty");
  const refreshButton = getElement<HTMLButtonElement>(
    "#monetization-refresh-btn",
  );
  const spinner = refreshButton?.querySelector(
    ".loading-spinner",
  ) as HTMLElement | null;

  if (loadingBlock) loadingBlock.style.display = loading ? "block" : "none";
  if (refreshButton) refreshButton.disabled = loading;
  if (spinner) spinner.style.display = loading ? "inline-block" : "none";

  if (loading) {
    if (tableWrapper) tableWrapper.style.display = "none";
    if (emptyBlock) emptyBlock.style.display = "none";
  }
}

function setFeedback(message: string, type: "info" | "error" = "info") {
  const alert = getElement<HTMLDivElement>("#monetization-feedback");
  if (!alert) return;
  if (!message) {
    alert.style.display = "none";
    alert.textContent = "";
    alert.className = "alert";
    return;
  }
  alert.style.display = "block";
  alert.textContent = message;
  alert.className = `alert ${type === "error" ? "alert-danger" : "alert-info"}`;
}

function formatRate(value: number | null | undefined): string {
  if (typeof value !== "number") return "N/A";
  return `${(value * 100).toFixed(1)}%`;
}

function formatDecimal(value: number | null | undefined): string {
  if (typeof value !== "number") return "N/A";
  return value.toFixed(2);
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const formatted = formatearMarcaTemporalEcuador(value);
  if (formatted !== "—") return formatted;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatter.format(date);
}

function statusBadge(
  status: MonetizationProviderRecord["billingStatus"],
): string {
  switch (status) {
    case "missing":
      return '<span class="badge bg-light text-dark border">Sin wallet</span>';
    case "paused_paywall":
      return '<span class="badge bg-danger">Pausada</span>';
    case "suspended":
      return '<span class="badge bg-secondary">Suspendido</span>';
    case "active":
    default:
      return '<span class="badge bg-success">Activa</span>';
  }
}

function describeScope(
  status: MonetizationOverview["scopeStatus"],
  generatedAt: string,
): string {
  const scopeLabel =
    status === "active"
      ? "Resumen filtrado: solo wallets activas."
      : status === "paused_paywall"
        ? "Resumen filtrado: solo wallets pausadas por saldo."
        : "Resumen global: todas las wallets.";
  return `${scopeLabel} Actualizado ${formatDate(generatedAt)}.`;
}

function describeFreshness(overview: MonetizationOverview): string {
  const parts = [
    `Wallets: ${formatDate(overview.latestWalletUpdateAt)}`,
    `Leads: ${formatDate(overview.latestLeadEventAt)}`,
    `Proveedores: ${formatDate(overview.latestProviderUpdateAt)}`,
    `Servicios: ${formatDate(overview.latestProviderServiceUpdateAt)}`,
  ];

  if (overview.latestFeedbackResponseAt) {
    parts.push(`Feedback: ${formatDate(overview.latestFeedbackResponseAt)}`);
  } else {
    parts.push("Feedback: sin respuestas registradas");
  }

  return parts.join(" | ");
}

function describeHealth(overview: MonetizationOverview): string {
  if (!overview.hasRecentLeadEvents30d) {
    return "Sin leads recientes en la ventana de 30 días.";
  }
  if (!overview.hasRecentFeedback30d) {
    return "Hay leads recientes, pero no hay feedback registrado en los últimos 30 días.";
  }
  return "Las señales operativas recientes están presentes en Supabase.";
}

function renderOverview() {
  const overview = state.overview;
  const active = getElement<HTMLElement>("#metric-active-wallets");
  const paused = getElement<HTMLElement>("#metric-paused-wallets");
  const leads7 = getElement<HTMLElement>("#metric-leads-7d");
  const leads30 = getElement<HTMLElement>("#metric-leads-30d");
  const paidLeads30 = getElement<HTMLElement>("#metric-paid-leads-30d");
  const feedbackCoverage = getElement<HTMLElement>(
    "#metric-feedback-coverage-30d",
  );
  const hireRateSent = getElement<HTMLElement>("#metric-hire-rate-sent-30d");
  const averageRating = getElement<HTMLElement>("#metric-average-rating-30d");
  const scopeNote = getElement<HTMLElement>("#monetization-scope-note");
  const freshnessNote = getElement<HTMLElement>("#monetization-freshness-note");
  const healthNote = getElement<HTMLElement>("#monetization-health-note");

  if (!overview) {
    if (active) active.textContent = "—";
    if (paused) paused.textContent = "—";
    if (leads7) leads7.textContent = "—";
    if (leads30) leads30.textContent = "—";
    if (paidLeads30) paidLeads30.textContent = "—";
    if (feedbackCoverage) feedbackCoverage.textContent = "—";
    if (hireRateSent) hireRateSent.textContent = "—";
    if (averageRating) averageRating.textContent = "—";
    if (scopeNote) scopeNote.textContent = "";
    if (freshnessNote) freshnessNote.textContent = "";
    if (healthNote) healthNote.textContent = "";
    return;
  }

  if (active) active.textContent = String(overview.activeWallets);
  if (paused) paused.textContent = String(overview.pausedWallets);
  if (leads7) leads7.textContent = String(overview.leadsShared7d);
  if (leads30) leads30.textContent = String(overview.leadsShared30d);
  if (paidLeads30) paidLeads30.textContent = String(overview.paidLeads30d);
  if (feedbackCoverage)
    feedbackCoverage.textContent = formatRate(overview.feedbackCoverage30d);
  if (hireRateSent)
    hireRateSent.textContent = formatRate(overview.hireRateOverSent30d);
  if (averageRating)
    averageRating.textContent = formatDecimal(overview.averageRating30d);
  if (scopeNote)
    scopeNote.textContent = describeScope(
      overview.scopeStatus,
      overview.generatedAt,
    );
  if (freshnessNote) freshnessNote.textContent = describeFreshness(overview);
  if (healthNote) healthNote.textContent = describeHealth(overview);
}

function renderTable() {
  const body = getElement<HTMLTableSectionElement>("#monetization-table-body");
  const tableWrapper = getElement<HTMLDivElement>(
    "#monetization-table-wrapper",
  );
  const emptyBlock = getElement<HTMLDivElement>("#monetization-empty");
  if (!body || !tableWrapper || !emptyBlock) return;

  if (state.providers.length === 0) {
    body.innerHTML = "";
    tableWrapper.style.display = "none";
    emptyBlock.style.display = "block";
    return;
  }

  emptyBlock.style.display = "none";
  tableWrapper.style.display = "block";
  body.innerHTML = state.providers
    .map(
      (provider) => `
      <tr>
        <td>
          <div class="fw-semibold">${provider.name}</div>
          <small class="text-muted">${
            formatearTelefonoEcuador(provider.phone) ?? "Sin teléfono"
          }</small>
        </td>
        <td>${provider.city ?? "—"}</td>
        <td>${statusBadge(provider.billingStatus)}</td>
        <td>${provider.freeLeadsRemaining}</td>
        <td>${provider.paidLeadsRemaining}</td>
        <td>${provider.paidLeads30d}</td>
        <td>${provider.freeLeads30d}</td>
        <td>${formatRate(provider.feedbackCoverage30d)}</td>
        <td>${formatRate(provider.hireRateOverSent30d)}</td>
        <td>${formatDecimal(provider.averageRating30d)}</td>
        <td><small class="text-muted">${formatDate(provider.lastLeadAt)}</small></td>
      </tr>
    `,
    )
    .join("");
}

async function loadMonetization() {
  setLoading(true);
  setFeedback("");
  try {
    const [overview, providersResponse] = await Promise.all([
      apiProveedores.obtenerMonetizacionResumen({
        status: state.filter,
      }),
      apiProveedores.obtenerMonetizacionProveedores({
        status: state.filter,
        limit: 100,
        offset: 0,
      }),
    ]);

    state.overview = overview;
    state.providers = providersResponse.items ?? [];
    renderOverview();
    renderTable();
  } catch (error) {
    console.error("Error cargando monetización:", error);
    setFeedback("No se pudo cargar la información de monetización.", "error");
    state.overview = null;
    state.providers = [];
    renderOverview();
    renderTable();
  } finally {
    setLoading(false);
  }
}

function bindEvents() {
  const refresh = getElement<HTMLButtonElement>("#monetization-refresh-btn");
  if (refresh) {
    refresh.addEventListener("click", () => {
      void loadMonetization();
    });
  }

  const filter = getElement<HTMLSelectElement>("#monetization-status-filter");
  if (filter) {
    filter.addEventListener("change", () => {
      const value = filter.value as BillingFilter;
      state.filter = value;
      void loadMonetization();
    });
  }
}

function init() {
  bindEvents();
  void loadMonetization();
}

export const MonetizationManager = {
  iniciar: init,
  recargar: loadMonetization,
};

export type MonetizationManagerModule = typeof MonetizationManager;
