import {
  apiProveedores,
  type ProviderStatusOverviewResponse,
} from "@tinkubot/api-client";

type DashboardState = {
  loading: boolean;
  summary: ProviderStatusOverviewResponse["summary"] | null;
};

const state: DashboardState = {
  loading: false,
  summary: null,
};

function getElement<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

function setValue(selector: string, value: string) {
  const element = getElement<HTMLElement>(selector);
  if (!element) return;
  element.textContent = value;
}

function renderSummary() {
  const summary = state.summary;
  setValue(
    "#dashboard-metric-new-pending",
    summary ? String(summary.newPending) : "—",
  );
  setValue(
    "#dashboard-metric-personal-approved",
    summary ? String(summary.personalApproved) : "—",
  );
  setValue(
    "#dashboard-metric-professional-to-complete",
    summary ? String(summary.professionalToComplete) : "—",
  );
  setValue(
    "#dashboard-metric-professional-under-review",
    summary ? String(summary.professionalUnderReview) : "—",
  );
  setValue(
    "#dashboard-metric-profile-complete",
    summary ? String(summary.profileComplete) : "—",
  );
}

async function recargar() {
  state.loading = true;
  try {
    const response = await apiProveedores.obtenerResumenEstadosProveedores();
    state.summary = response.summary;
    renderSummary();
  } catch (error) {
    console.error("Error cargando resumen del dashboard:", error);
    state.summary = null;
    renderSummary();
  } finally {
    state.loading = false;
  }
}

function iniciar() {
  void recargar();
}

export const DashboardManager = {
  iniciar,
  recargar,
};

export type DashboardManagerModule = typeof DashboardManager;
