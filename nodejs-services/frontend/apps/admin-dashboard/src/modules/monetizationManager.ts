import {
  apiProveedores,
  type MonetizationOverview,
  type MonetizationProviderRecord
} from '@tinkubot/api-client';

type BillingFilter = 'all' | 'active' | 'paused_paywall' | 'suspended';

interface MonetizationState {
  loading: boolean;
  filter: BillingFilter;
  overview: MonetizationOverview | null;
  providers: MonetizationProviderRecord[];
}

const state: MonetizationState = {
  loading: false,
  filter: 'all',
  overview: null,
  providers: []
};

const formatter = new Intl.DateTimeFormat('es-EC', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'America/Guayaquil'
});

function getElement<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

function setLoading(loading: boolean) {
  state.loading = loading;
  const loadingBlock = getElement<HTMLDivElement>('#monetization-loading');
  const tableWrapper = getElement<HTMLDivElement>('#monetization-table-wrapper');
  const emptyBlock = getElement<HTMLDivElement>('#monetization-empty');
  const refreshButton = getElement<HTMLButtonElement>('#monetization-refresh-btn');
  const spinner = refreshButton?.querySelector('.loading-spinner') as HTMLElement | null;

  if (loadingBlock) loadingBlock.style.display = loading ? 'block' : 'none';
  if (refreshButton) refreshButton.disabled = loading;
  if (spinner) spinner.style.display = loading ? 'inline-block' : 'none';

  if (loading) {
    if (tableWrapper) tableWrapper.style.display = 'none';
    if (emptyBlock) emptyBlock.style.display = 'none';
  }
}

function setFeedback(message: string, type: 'info' | 'error' = 'info') {
  const alert = getElement<HTMLDivElement>('#monetization-feedback');
  if (!alert) return;
  if (!message) {
    alert.style.display = 'none';
    alert.textContent = '';
    alert.className = 'alert';
    return;
  }
  alert.style.display = 'block';
  alert.textContent = message;
  alert.className = `alert ${type === 'error' ? 'alert-danger' : 'alert-info'}`;
}

function formatRate(value: number | null | undefined): string {
  if (typeof value !== 'number') return 'N/A';
  return `${(value * 100).toFixed(1)}%`;
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatter.format(date);
}

function statusBadge(status: MonetizationProviderRecord['billingStatus']): string {
  switch (status) {
    case 'paused_paywall':
      return '<span class="badge bg-danger">Pausado</span>';
    case 'suspended':
      return '<span class="badge bg-secondary">Suspendido</span>';
    case 'active':
    default:
      return '<span class="badge bg-success">Activo</span>';
  }
}

function renderOverview() {
  const overview = state.overview;
  const active = getElement<HTMLElement>('#metric-active-providers');
  const paused = getElement<HTMLElement>('#metric-paused-providers');
  const leads7 = getElement<HTMLElement>('#metric-leads-7d');
  const leads30 = getElement<HTMLElement>('#metric-leads-30d');
  const hiredRate = getElement<HTMLElement>('#metric-hired-rate-30d');

  if (!overview) {
    if (active) active.textContent = '—';
    if (paused) paused.textContent = '—';
    if (leads7) leads7.textContent = '—';
    if (leads30) leads30.textContent = '—';
    if (hiredRate) hiredRate.textContent = '—';
    return;
  }

  if (active) active.textContent = String(overview.activeProviders);
  if (paused) paused.textContent = String(overview.pausedProviders);
  if (leads7) leads7.textContent = String(overview.leadsShared7d);
  if (leads30) leads30.textContent = String(overview.leadsShared30d);
  if (hiredRate) hiredRate.textContent = formatRate(overview.hiredRate30d);
}

function renderTable() {
  const body = getElement<HTMLTableSectionElement>('#monetization-table-body');
  const tableWrapper = getElement<HTMLDivElement>('#monetization-table-wrapper');
  const emptyBlock = getElement<HTMLDivElement>('#monetization-empty');
  if (!body || !tableWrapper || !emptyBlock) return;

  if (state.providers.length === 0) {
    body.innerHTML = '';
    tableWrapper.style.display = 'none';
    emptyBlock.style.display = 'block';
    return;
  }

  emptyBlock.style.display = 'none';
  tableWrapper.style.display = 'block';
  body.innerHTML = state.providers
    .map(
      provider => `
      <tr>
        <td>
          <div class="fw-semibold">${provider.name}</div>
          <small class="text-muted">${provider.phone ?? 'Sin teléfono'}</small>
        </td>
        <td>${provider.city ?? '—'}</td>
        <td>${statusBadge(provider.billingStatus)}</td>
        <td>${provider.freeLeadsRemaining}</td>
        <td>${provider.paidLeadsRemaining}</td>
        <td>${provider.leadsShared30d}</td>
        <td>${provider.hiredYes30d} / ${provider.hiredNo30d}</td>
        <td><small class="text-muted">${formatDate(provider.lastLeadAt)}</small></td>
      </tr>
    `
    )
    .join('');
}

async function loadMonetization() {
  setLoading(true);
  setFeedback('');
  try {
    const [overview, providersResponse] = await Promise.all([
      apiProveedores.obtenerMonetizacionResumen(),
      apiProveedores.obtenerMonetizacionProveedores({
        status: state.filter,
        limit: 100,
        offset: 0
      })
    ]);

    state.overview = overview;
    state.providers = providersResponse.items ?? [];
    renderOverview();
    renderTable();
  } catch (error) {
    console.error('Error cargando monetización:', error);
    setFeedback('No se pudo cargar la información de monetización.', 'error');
    state.overview = null;
    state.providers = [];
    renderOverview();
    renderTable();
  } finally {
    setLoading(false);
  }
}

function bindEvents() {
  const refresh = getElement<HTMLButtonElement>('#monetization-refresh-btn');
  if (refresh) {
    refresh.addEventListener('click', () => {
      void loadMonetization();
    });
  }

  const filter = getElement<HTMLSelectElement>('#monetization-status-filter');
  if (filter) {
    filter.addEventListener('change', () => {
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
  recargar: loadMonetization
};

export type MonetizationManagerModule = typeof MonetizationManager;
