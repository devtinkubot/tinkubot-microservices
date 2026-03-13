import {
  apiProveedores,
  type ServiceGovernanceApprovePayload,
  type ServiceGovernanceDomainRecord,
  type ServiceGovernanceMetricsResponse,
  type ServiceGovernanceReviewRecord,
  type ServiceGovernanceReviewStatus
} from '@tinkubot/api-client';

type GovernanceFilter =
  | 'all'
  | 'pending'
  | 'approved_existing_domain'
  | 'approved_new_domain'
  | 'rejected';

type AlertType = 'info' | 'error' | 'success';

interface GovernanceState {
  loading: boolean;
  filter: GovernanceFilter;
  reviews: ServiceGovernanceReviewRecord[];
  domains: ServiceGovernanceDomainRecord[];
  metrics: ServiceGovernanceMetricsResponse | null;
  selectedReviewId: string | null;
  actionInFlight: boolean;
}

const state: GovernanceState = {
  loading: false,
  filter: 'pending',
  reviews: [],
  domains: [],
  metrics: null,
  selectedReviewId: null,
  actionInFlight: false
};

const formatter = new Intl.DateTimeFormat('es-EC', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'America/Guayaquil'
});

function getElement<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, char => {
    const map: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    };
    return map[char] ?? char;
  });
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatter.format(date);
}

function setFeedback(message: string, type: AlertType = 'info') {
  const alert = getElement<HTMLDivElement>('#governance-feedback');
  if (!alert) return;
  if (!message) {
    alert.style.display = 'none';
    alert.textContent = '';
    alert.className = 'alert';
    return;
  }
  alert.style.display = 'block';
  alert.textContent = message;
  alert.className = `alert ${
    type === 'error' ? 'alert-danger' : type === 'success' ? 'alert-success' : 'alert-info'
  }`;
}

function setLoading(loading: boolean) {
  state.loading = loading;
  const loadingBlock = getElement<HTMLDivElement>('#governance-loading');
  const tableWrapper = getElement<HTMLDivElement>('#governance-table-wrapper');
  const emptyBlock = getElement<HTMLDivElement>('#governance-empty');
  const refreshButton = getElement<HTMLButtonElement>('#governance-refresh-btn');
  const spinner = refreshButton?.querySelector('.loading-spinner') as HTMLElement | null;

  if (loadingBlock) loadingBlock.style.display = loading ? 'block' : 'none';
  if (refreshButton) refreshButton.disabled = loading || state.actionInFlight;
  if (spinner) spinner.style.display = loading ? 'inline-block' : 'none';
  if (loading) {
    if (tableWrapper) tableWrapper.style.display = 'none';
    if (emptyBlock) emptyBlock.style.display = 'none';
  }
}

function selectedReview(): ServiceGovernanceReviewRecord | null {
  return state.reviews.find(item => item.id === state.selectedReviewId) ?? null;
}

function statusBadge(status: ServiceGovernanceReviewStatus): string {
  switch (status) {
    case 'approved_existing_domain':
      return '<span class="badge bg-success">Aprobado dominio existente</span>';
    case 'approved_new_domain':
      return '<span class="badge bg-primary">Aprobado dominio nuevo</span>';
    case 'rejected':
      return '<span class="badge bg-danger">Rechazado</span>';
    case 'pending':
    default:
      return '<span class="badge bg-warning text-dark">Pendiente</span>';
  }
}

function renderMetrics() {
  const metrics = state.metrics;
  const pending = getElement<HTMLElement>('#governance-metric-pending');
  const approved = getElement<HTMLElement>('#governance-metric-approved');
  const rejected = getElement<HTMLElement>('#governance-metric-rejected');
  const domains = getElement<HTMLElement>('#governance-metric-domains');
  const services = getElement<HTMLElement>('#governance-metric-services');
  const topDomains = getElement<HTMLElement>('#governance-top-domains');

  if (!metrics) {
    [pending, approved, rejected, domains, services, topDomains].forEach(item => {
      if (item) item.textContent = '—';
    });
    return;
  }

  if (pending) pending.textContent = String(metrics.summary.pending);
  if (approved) {
    approved.textContent = String(
      metrics.summary.approvedExistingDomain + metrics.summary.approvedNewDomain
    );
  }
  if (rejected) rejected.textContent = String(metrics.summary.rejected);
  if (domains) domains.textContent = String(metrics.summary.activeDomains);
  if (services) services.textContent = String(metrics.summary.operationalServices);
  if (topDomains) {
    const text = metrics.topSuggestedDomains
      .map(item => `${item.domainCode} (${item.count})`)
      .join(' · ');
    topDomains.textContent = text || 'Sin señales todavía';
  }
}

function fillApproveForm(review: ServiceGovernanceReviewRecord) {
  const domainSelect = getElement<HTMLSelectElement>('#governance-domain-select');
  const categoryInput = getElement<HTMLInputElement>('#governance-category-input');
  const serviceInput = getElement<HTMLInputElement>('#governance-service-input');
  const summaryInput = getElement<HTMLTextAreaElement>('#governance-summary-input');
  if (!domainSelect || !categoryInput || !serviceInput || !summaryInput) return;

  const currentDomain = review.assignedDomainCode || review.suggestedDomainCode || '';
  domainSelect.innerHTML =
    '<option value="">Selecciona un dominio</option>' +
    state.domains
      .map(
        item =>
          `<option value="${escapeHtml(item.code)}" ${
            item.code === currentDomain ? 'selected' : ''
          }>${escapeHtml(item.displayName)}</option>`
      )
      .join('');
  if (currentDomain && !state.domains.some(item => item.code === currentDomain)) {
    domainSelect.insertAdjacentHTML(
      'beforeend',
      `<option value="${escapeHtml(currentDomain)}" selected>${escapeHtml(currentDomain)} (nuevo)</option>`
    );
  }

  categoryInput.value = review.assignedCategoryName || review.proposedCategoryName || '';
  serviceInput.value = review.assignedServiceName || review.serviceName || '';
  summaryInput.value =
    review.assignedServiceSummary || review.proposedServiceSummary || '';
}

function renderDetail() {
  const panel = getElement<HTMLDivElement>('#governance-detail-panel');
  if (!panel) return;
  const review = selectedReview();
  if (!review) {
    panel.innerHTML =
      '<div class="text-muted">Selecciona un servicio en revisión para ver el detalle y resolverlo.</div>';
    return;
  }

  panel.innerHTML = `
    <div class="mb-3">
      <div class="small text-muted">Servicio original</div>
      <div class="fw-semibold">${escapeHtml(review.rawServiceText)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Servicio visible sugerido</div>
      <div>${escapeHtml(review.serviceName)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Proveedor</div>
      <div>${escapeHtml(review.providerName || 'Proveedor sin nombre')}</div>
      <div class="small text-muted">${escapeHtml(review.providerPhone || 'Sin teléfono')} · ${escapeHtml(review.providerCity || 'Sin ciudad')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Motivo</div>
      <div>${escapeHtml(review.reviewReason || 'Sin motivo')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Servicios operativos del proveedor</div>
      <div>${
        review.currentProviderServices && review.currentProviderServices.length > 0
          ? review.currentProviderServices
              .map(item => `<span class="provider-service-badge">${escapeHtml(item)}</span>`)
              .join('')
          : '<span class="text-muted">No tiene servicios operativos todavía</span>'
      }</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Estado</div>
      <div>${statusBadge(review.reviewStatus)}</div>
    </div>
    <hr />
    <div class="mb-2 fw-semibold">Resolver revisión</div>
    <div class="mb-3">
      <label class="form-label small text-muted" for="governance-domain-select">Dominio final</label>
      <select class="form-select form-select-sm" id="governance-domain-select"></select>
    </div>
    <div class="mb-3">
      <label class="form-label small text-muted" for="governance-category-input">Categoría final</label>
      <input class="form-control form-control-sm" id="governance-category-input" type="text" />
    </div>
    <div class="mb-3">
      <label class="form-label small text-muted" for="governance-service-input">Servicio visible final</label>
      <input class="form-control form-control-sm" id="governance-service-input" type="text" />
    </div>
    <div class="mb-3">
      <label class="form-label small text-muted" for="governance-summary-input">Resumen final</label>
      <textarea class="form-control form-control-sm" id="governance-summary-input" rows="4"></textarea>
    </div>
    <div class="form-check mb-3">
      <input class="form-check-input" type="checkbox" id="governance-create-domain" />
      <label class="form-check-label small" for="governance-create-domain">
        Crear dominio si no existe
      </label>
    </div>
    <div class="mb-3">
      <label class="form-label small text-muted" for="governance-reviewer-input">Revisor</label>
      <input class="form-control form-control-sm" id="governance-reviewer-input" type="text" value="admin-dashboard" />
    </div>
    <div class="mb-3">
      <label class="form-label small text-muted" for="governance-notes-input">Notas</label>
      <textarea class="form-control form-control-sm" id="governance-notes-input" rows="3"></textarea>
    </div>
    <div class="d-flex gap-2">
      <button class="btn btn-success btn-sm" id="governance-approve-btn" type="button">
        Aprobar y publicar
      </button>
      <button class="btn btn-outline-danger btn-sm" id="governance-reject-btn" type="button">
        Rechazar
      </button>
    </div>
  `;

  fillApproveForm(review);
  getElement<HTMLButtonElement>('#governance-approve-btn')?.addEventListener('click', () => {
    void approveSelected();
  });
  getElement<HTMLButtonElement>('#governance-reject-btn')?.addEventListener('click', () => {
    void rejectSelected();
  });
}

function renderTable() {
  const body = getElement<HTMLTableSectionElement>('#governance-table-body');
  const wrapper = getElement<HTMLDivElement>('#governance-table-wrapper');
  const empty = getElement<HTMLDivElement>('#governance-empty');
  if (!body || !wrapper || !empty) return;

  if (state.reviews.length === 0) {
    body.innerHTML = '';
    wrapper.style.display = 'none';
    empty.style.display = 'block';
    renderDetail();
    return;
  }

  empty.style.display = 'none';
  wrapper.style.display = 'flex';
  body.innerHTML = state.reviews
    .map(
      review => `
        <tr data-governance-review="${escapeHtml(review.id)}" class="${
          review.id === state.selectedReviewId ? 'table-active' : ''
        }">
          <td>
            <div class="fw-semibold">${escapeHtml(review.serviceName)}</div>
            <small class="text-muted">${escapeHtml(review.rawServiceText || review.serviceName)}</small>
          </td>
          <td>
            <div>${escapeHtml(review.providerName || 'Proveedor sin nombre')}</div>
            <small class="text-muted">${escapeHtml(review.providerCity || 'Sin ciudad')}</small>
          </td>
          <td>${escapeHtml(review.suggestedDomainCode || 'Sin sugerencia')}</td>
          <td>${statusBadge(review.reviewStatus)}</td>
          <td>${formatDate(review.createdAt)}</td>
        </tr>
      `
    )
    .join('');

  body.querySelectorAll<HTMLTableRowElement>('tr[data-governance-review]').forEach(row => {
    row.addEventListener('click', () => {
      state.selectedReviewId = row.dataset.governanceReview ?? null;
      renderTable();
      renderDetail();
    });
  });

  if (!state.selectedReviewId && state.reviews[0]) {
    state.selectedReviewId = state.reviews[0].id;
    renderTable();
    renderDetail();
  }
}

function approvalPayload(): ServiceGovernanceApprovePayload | null {
  const domainCode = getElement<HTMLSelectElement>('#governance-domain-select')?.value?.trim() || '';
  const categoryName = getElement<HTMLInputElement>('#governance-category-input')?.value?.trim() || '';
  const serviceName = getElement<HTMLInputElement>('#governance-service-input')?.value?.trim() || '';
  const serviceSummary =
    getElement<HTMLTextAreaElement>('#governance-summary-input')?.value?.trim() || '';
  const reviewer =
    getElement<HTMLInputElement>('#governance-reviewer-input')?.value?.trim() || 'admin-dashboard';
  const notes = getElement<HTMLTextAreaElement>('#governance-notes-input')?.value?.trim() || '';
  const createDomainIfMissing = Boolean(
    getElement<HTMLInputElement>('#governance-create-domain')?.checked
  );

  if (!domainCode || !categoryName || !serviceName) {
    setFeedback('Debes completar dominio, categoría y servicio final.', 'error');
    return null;
  }

  return {
    domainCode,
    categoryName,
    serviceName,
    serviceSummary,
    reviewer,
    notes,
    createDomainIfMissing
  };
}

async function approveSelected() {
  const review = selectedReview();
  const payload = approvalPayload();
  if (!review || !payload) return;
  try {
    state.actionInFlight = true;
    setLoading(state.loading);
    const result = await apiProveedores.aprobarGovernanceReview(review.id, payload);
    if (!result.success) {
      throw new Error(result.message || 'No se pudo aprobar la revisión.');
    }
    setFeedback('Servicio aprobado y publicado correctamente.', 'success');
    await recargar();
  } catch (error) {
    setFeedback(
      error instanceof Error ? error.message : 'No se pudo aprobar la revisión.',
      'error'
    );
  } finally {
    state.actionInFlight = false;
    setLoading(state.loading);
  }
}

async function rejectSelected() {
  const review = selectedReview();
  if (!review) return;
  try {
    state.actionInFlight = true;
    setLoading(state.loading);
    const reviewer =
      getElement<HTMLInputElement>('#governance-reviewer-input')?.value?.trim() || 'admin-dashboard';
    const notes = getElement<HTMLTextAreaElement>('#governance-notes-input')?.value?.trim() || '';
    const result = await apiProveedores.rechazarGovernanceReview(review.id, {
      reviewer,
      notes
    });
    if (!result.success) {
      throw new Error(result.message || 'No se pudo rechazar la revisión.');
    }
    setFeedback('Revisión rechazada correctamente.', 'success');
    await recargar();
  } catch (error) {
    setFeedback(
      error instanceof Error ? error.message : 'No se pudo rechazar la revisión.',
      'error'
    );
  } finally {
    state.actionInFlight = false;
    setLoading(state.loading);
  }
}

async function recargar() {
  setLoading(true);
  try {
    const [reviewsResult, domainsResult, metricsResult] = await Promise.all([
      apiProveedores.obtenerGovernanceReviews({
        status: state.filter,
        limit: 100
      }),
      apiProveedores.obtenerGovernanceDomains(),
      apiProveedores.obtenerGovernanceMetrics()
    ]);
    state.reviews = reviewsResult.reviews || [];
    state.domains = domainsResult.domains || [];
    state.metrics = metricsResult;
    if (!state.reviews.some(item => item.id === state.selectedReviewId)) {
      state.selectedReviewId = state.reviews[0]?.id ?? null;
    }
    renderMetrics();
    renderTable();
    renderDetail();
  } catch (error) {
    setFeedback(
      error instanceof Error ? error.message : 'No se pudo cargar la gobernanza de servicios.',
      'error'
    );
  } finally {
    setLoading(false);
  }
}

function bindEvents() {
  getElement<HTMLButtonElement>('#governance-refresh-btn')?.addEventListener('click', () => {
    void recargar();
  });
  getElement<HTMLSelectElement>('#governance-status-filter')?.addEventListener('change', event => {
    const target = event.currentTarget as HTMLSelectElement;
    state.filter = (target.value as GovernanceFilter) || 'pending';
    void recargar();
  });
}

function iniciar() {
  bindEvents();
  void recargar();
}

export const GovernanceManager = {
  iniciar,
  recargar
};

export type GovernanceManagerModule = typeof GovernanceManager;
