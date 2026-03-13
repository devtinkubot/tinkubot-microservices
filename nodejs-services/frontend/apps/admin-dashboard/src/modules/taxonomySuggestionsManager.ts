import {
  apiProveedores,
  type TaxonomyCatalogDomain,
  type TaxonomyCatalogResponse,
  type TaxonomyDraftPayload,
  type TaxonomyDraftRecord,
  type TaxonomySuggestionCluster,
  type TaxonomyOverviewResponse,
  type TaxonomySuggestionRecord,
  type TaxonomySuggestionStatus
} from '@tinkubot/api-client';

type SuggestionFilter = 'all' | 'pending' | 'enriched' | 'approved' | 'rejected' | 'superseded';
type AlertType = 'info' | 'error' | 'success';

interface TaxonomyState {
  loading: boolean;
  filter: SuggestionFilter;
  overview: TaxonomyOverviewResponse | null;
  catalog: TaxonomyCatalogResponse | null;
  items: TaxonomySuggestionCluster[];
  drafts: TaxonomyDraftRecord[];
  selectedDomainCode: string | null;
  selectedId: string | null;
  selectedDraftId: string | null;
  actionInFlightId: string | null;
}

const state: TaxonomyState = {
  loading: false,
  filter: 'pending',
  overview: null,
  catalog: null,
  items: [],
  drafts: [],
  selectedDomainCode: null,
  selectedId: null,
  selectedDraftId: null,
  actionInFlightId: null
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

function setLoading(loading: boolean) {
  state.loading = loading;
  const loadingBlock = getElement<HTMLDivElement>('#taxonomy-loading');
  const catalogWrapper = getElement<HTMLDivElement>('#taxonomy-catalog-wrapper');
  const catalogEmpty = getElement<HTMLDivElement>('#taxonomy-catalog-empty');
  const tableWrapper = getElement<HTMLDivElement>('#taxonomy-table-wrapper');
  const emptyBlock = getElement<HTMLDivElement>('#taxonomy-empty');
  const refreshButton = getElement<HTMLButtonElement>('#taxonomy-refresh-btn');
  const spinner = refreshButton?.querySelector('.loading-spinner') as HTMLElement | null;

  if (loadingBlock) loadingBlock.style.display = loading ? 'block' : 'none';
  if (refreshButton) refreshButton.disabled = loading;
  if (spinner) spinner.style.display = loading ? 'inline-block' : 'none';

  if (loading) {
    if (catalogWrapper) catalogWrapper.style.display = 'none';
    if (catalogEmpty) catalogEmpty.style.display = 'none';
    if (tableWrapper) tableWrapper.style.display = 'none';
    if (emptyBlock) emptyBlock.style.display = 'none';
  }
}

function setFeedback(message: string, type: AlertType = 'info') {
  const alert = getElement<HTMLDivElement>('#taxonomy-feedback');
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

function proposalBadge(type?: string | null): string {
  switch (type) {
    case 'alias':
      return '<span class="badge bg-primary">Alias</span>';
    case 'new_canonical':
      return '<span class="badge bg-success">Nuevo canónico</span>';
    case 'rule_update':
      return '<span class="badge bg-info text-dark">Regla</span>';
    case 'reject':
      return '<span class="badge bg-danger">Rechazar</span>';
    case 'review':
    default:
      return '<span class="badge bg-secondary">Revisar</span>';
  }
}

function statusBadge(status: TaxonomySuggestionStatus): string {
  switch (status) {
    case 'approved':
      return '<span class="badge bg-success">Aprobada</span>';
    case 'rejected':
      return '<span class="badge bg-danger">Rechazada</span>';
    case 'superseded':
      return '<span class="badge bg-dark">Reemplazada</span>';
    case 'enriched':
      return '<span class="badge bg-primary">Enriquecida</span>';
    case 'pending':
    default:
      return '<span class="badge bg-warning text-dark">Pendiente</span>';
  }
}

function confidenceText(value?: number | null): string {
  if (typeof value !== 'number') return '—';
  return `${(value * 100).toFixed(0)}%`;
}

function renderOverview() {
  const overview = state.overview;
  const version = getElement<HTMLDivElement>('#taxonomy-overview-version');
  const publishedAt = getElement<HTMLDivElement>('#taxonomy-overview-published-at');
  const coverage = getElement<HTMLDivElement>('#taxonomy-overview-coverage');
  const coverageDetail = getElement<HTMLDivElement>('#taxonomy-overview-coverage-detail');
  const suggestions = getElement<HTMLDivElement>('#taxonomy-overview-suggestions');
  const suggestionsDetail = getElement<HTMLDivElement>('#taxonomy-overview-suggestions-detail');
  const drafts = getElement<HTMLDivElement>('#taxonomy-overview-drafts');
  const draftsDetail = getElement<HTMLDivElement>('#taxonomy-overview-drafts-detail');
  const runtime = getElement<HTMLDivElement>('#taxonomy-overview-runtime');
  const runtimeDetail = getElement<HTMLDivElement>('#taxonomy-overview-runtime-detail');

  if (!version || !publishedAt || !coverage || !coverageDetail || !suggestions || !suggestionsDetail || !drafts || !draftsDetail || !runtime || !runtimeDetail) {
    return;
  }

  if (!overview) {
    version.textContent = '—';
    publishedAt.textContent = '—';
    coverage.textContent = '—';
    coverageDetail.textContent = '—';
    suggestions.textContent = '—';
    suggestionsDetail.textContent = '—';
    drafts.textContent = '—';
    draftsDetail.textContent = '—';
    runtime.textContent = '—';
    runtimeDetail.textContent = '—';
    return;
  }

  version.textContent =
    typeof overview.summary.activeVersion === 'number'
      ? `v${overview.summary.activeVersion}`
      : 'Sin publicar';
  publishedAt.textContent = overview.summary.publishedAt
    ? `Publicado: ${formatDate(overview.summary.publishedAt)}`
    : 'Sin publicación activa';
  coverage.textContent = String(overview.summary.domainsPublished ?? 0);
  coverageDetail.textContent = `Reglas: ${overview.summary.domainsWithRules} · Aliases: ${overview.summary.domainsWithAliases} · Canónicos: ${overview.summary.domainsWithCanonicals}`;
  suggestions.textContent = String(overview.summary.totalSuggestions ?? 0);
  suggestionsDetail.textContent = `Pendientes: ${overview.suggestionStatusCounts.pending} · Rechazadas: ${overview.suggestionStatusCounts.rejected} · Cliente/Proveedor: ${overview.suggestionSourceCounts.client}/${overview.suggestionSourceCounts.provider}`;
  drafts.textContent = String(overview.summary.totalDrafts ?? 0);
  draftsDetail.textContent = `Borrador: ${overview.draftStatusCounts.draft} · Aplicado: ${overview.draftStatusCounts.applied} · Publicado: ${overview.draftStatusCounts.published}`;
  runtime.textContent = String(overview.runtimeMetrics7d.totalEvents ?? 0);
  const topDomains = overview.runtimeMetrics7d.topAmbiguousDomains
    .slice(0, 3)
    .map(item => `${item.domainCode}: ${item.clarificationRequested}`)
    .join(' · ');
  runtimeDetail.textContent =
    `Repreguntas: ${overview.runtimeMetrics7d.eventCounts.clarificationRequested} · Respaldo legacy: ${overview.runtimeMetrics7d.eventCounts.genericFallbackUsed} · Cliente/Proveedor: ${overview.runtimeMetrics7d.sourceCounts.client}/${overview.runtimeMetrics7d.sourceCounts.provider}` +
    (topDomains ? ` · Top: ${topDomains}` : '');
}

function selectedCatalogDomain(): TaxonomyCatalogDomain | null {
  const domains = state.catalog?.domains ?? [];
  return domains.find(item => item.code === state.selectedDomainCode) ?? null;
}

function renderCatalogTable() {
  const body = getElement<HTMLTableSectionElement>('#taxonomy-catalog-table-body');
  const wrapper = getElement<HTMLDivElement>('#taxonomy-catalog-wrapper');
  const empty = getElement<HTMLDivElement>('#taxonomy-catalog-empty');
  if (!body || !wrapper || !empty) return;

  const domains = state.catalog?.domains ?? [];
  if (domains.length === 0) {
    body.innerHTML = '';
    wrapper.style.display = 'none';
    empty.style.display = 'block';
    renderCatalogDetail();
    return;
  }

  empty.style.display = 'none';
  wrapper.style.display = 'flex';
  body.innerHTML = domains
    .map(
      domain => `
      <tr data-taxonomy-domain="${escapeHtml(domain.code)}" class="${
        domain.code === state.selectedDomainCode ? 'table-active' : ''
      }">
        <td>
          <div class="fw-semibold">${escapeHtml(domain.displayName ?? domain.code)}</div>
          <small class="text-muted">${escapeHtml(domain.code)}</small>
        </td>
        <td>${domain.canonicalServices.length}</td>
        <td>${domain.aliases.length}</td>
        <td>${domain.rules.length}</td>
      </tr>
    `
    )
    .join('');

  body.querySelectorAll<HTMLTableRowElement>('tr[data-taxonomy-domain]').forEach(row => {
    row.addEventListener('click', () => {
      state.selectedDomainCode = row.dataset.taxonomyDomain ?? null;
      renderCatalogTable();
      renderCatalogDetail();
    });
  });

  if (!state.selectedDomainCode && domains[0]) {
    state.selectedDomainCode = domains[0].code;
    renderCatalogTable();
    renderCatalogDetail();
  }
}

function renderCatalogDetail() {
  const panel = getElement<HTMLDivElement>('#taxonomy-catalog-detail-panel');
  if (!panel) return;

  const domain = selectedCatalogDomain();
  if (!domain) {
    panel.innerHTML =
      '<div class="text-muted">Selecciona un dominio para ver aliases, canónicos y reglas activas.</div>';
    return;
  }

  const requiredDimensions = domain.rules.flatMap(rule => rule.required_dimensions ?? []);
  const genericExamples = domain.rules.flatMap(rule => rule.generic_examples ?? []).slice(0, 6);
  const sufficientExamples = domain.rules
    .flatMap(rule => rule.sufficient_examples ?? [])
    .slice(0, 6);

  panel.innerHTML = `
    <div class="mb-3">
      <div class="small text-muted">Dominio</div>
      <div class="fw-semibold">${escapeHtml(domain.displayName ?? domain.code)}</div>
      <div class="small text-muted">${escapeHtml(domain.code)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Servicios canónicos</div>
      <div>${renderList(domain.canonicalServices.map(item => item.canonical_name ?? ''))}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Aliases</div>
      <div>${renderList(domain.aliases.map(item => item.alias_text ?? item.alias_normalized ?? ''))}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Dimensiones requeridas</div>
      <div>${renderList(requiredDimensions)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Ejemplos genéricos</div>
      <div>${renderList(genericExamples)}</div>
    </div>
    <div class="mb-0">
      <div class="small text-muted">Ejemplos suficientes</div>
      <div>${renderList(sufficientExamples)}</div>
    </div>
  `;
}

function renderList(items?: string[] | null): string {
  if (!items || items.length === 0) return '—';
  return items.map(item => `<span class="badge bg-light text-dark border me-1 mb-1">${escapeHtml(item)}</span>`).join('');
}

function payloadForDraft(draft: TaxonomyDraftRecord): TaxonomyDraftPayload | null {
  return draft.payload_json ?? null;
}

function selectedCluster(): TaxonomySuggestionCluster | null {
  return state.items.find(item => item.clusterId === state.selectedId) ?? null;
}

function selectedSuggestion(): TaxonomySuggestionRecord | null {
  return selectedCluster()?.representative ?? null;
}

function renderDetail() {
  const suggestion = selectedSuggestion();
  const cluster = selectedCluster();
  const panel = getElement<HTMLDivElement>('#taxonomy-detail-panel');
  if (!panel) return;

  if (!suggestion || !cluster) {
    panel.innerHTML = `
      <div class="text-muted">
        Selecciona un caso para ver evidencia, propuesta y contexto.
      </div>
    `;
    return;
  }

  const alias = suggestion.evidence_json?.alias_match;
  const providerMatch = suggestion.evidence_json?.provider_service_match;
  const notesPlaceholder =
    cluster.reviewStatus === 'rejected'
      ? 'Este caso ya está rechazado.'
      : 'Puedes marcar este caso como rechazado si es ruido.';

  panel.innerHTML = `
    <div class="mb-3">
      <div class="d-flex gap-2 align-items-center flex-wrap">
        ${proposalBadge(suggestion.proposal_type)}
        ${statusBadge(suggestion.review_status)}
        <span class="text-muted small">Confianza: ${confidenceText(
          suggestion.confidence_score
        )}</span>
      </div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Texto original</div>
      <div class="fw-semibold">${escapeHtml(suggestion.source_text ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Caso agrupado</div>
      <div>${cluster.memberCount} miembros · ${cluster.totalOccurrences} ocurrencias</div>
      <div class="small text-muted">${escapeHtml(cluster.variants.join(' · ') || '—')}</div>
      <div class="small text-muted">
        Cliente/Proveedor/Admin/System: ${cluster.sourceCounts.client}/${cluster.sourceCounts.provider}/${cluster.sourceCounts.admin}/${cluster.sourceCounts.system}
      </div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Normalizado</div>
      <div>${escapeHtml(suggestion.normalized_text)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Dominio propuesto</div>
      <div>${escapeHtml(suggestion.proposed_domain_code ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Canónico sugerido</div>
      <div>${escapeHtml(suggestion.proposed_canonical_name ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Servicio candidato</div>
      <div>${escapeHtml(suggestion.proposed_service_candidate ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Dimensiones faltantes</div>
      <div>${renderList(suggestion.missing_dimensions)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Contexto</div>
      <div>${escapeHtml(suggestion.context_excerpt ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Evidencia alias</div>
      <div>${alias ? `${escapeHtml(alias.alias_text ?? '—')} (${confidenceText(alias.similarity)})` : 'Sin match'}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Evidencia provider_services</div>
      <div>${
        providerMatch
          ? `${escapeHtml(providerMatch.service_name ?? '—')} (${confidenceText(providerMatch.similarity)})`
          : 'Sin match'
      }</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Visto</div>
      <div>${suggestion.occurrence_count ?? 1} veces. Última vez: ${formatDate(
        suggestion.last_seen_at
      )}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Variantes agrupadas</div>
      <div>${renderList(cluster.members.map(member => member.source_text ?? member.normalized_text))}</div>
    </div>
    <div class="d-flex gap-2 flex-wrap">
      <button
        type="button"
        class="btn btn-primary btn-sm"
        id="taxonomy-approve-btn"
        ${cluster.reviewStatus === 'approved' ? 'disabled' : ''}
      >
        Aprobar a draft
      </button>
      <button
        type="button"
        class="btn btn-outline-danger btn-sm"
        id="taxonomy-reject-btn"
        ${cluster.reviewStatus === 'rejected' ? 'disabled' : ''}
      >
        Marcar rechazada
      </button>
      <button
        type="button"
        class="btn btn-outline-secondary btn-sm"
        id="taxonomy-restore-btn"
        ${cluster.reviewStatus === 'pending' ? 'disabled' : ''}
      >
        Volver a pendiente
      </button>
      <span class="text-muted small align-self-center">${escapeHtml(notesPlaceholder)}</span>
    </div>
  `;

  getElement<HTMLButtonElement>('#taxonomy-approve-btn')?.addEventListener('click', () => {
    void approveCluster(cluster.clusterId);
  });
  getElement<HTMLButtonElement>('#taxonomy-reject-btn')?.addEventListener('click', () => {
    void reviewCluster(cluster.clusterId, 'rejected');
  });
  getElement<HTMLButtonElement>('#taxonomy-restore-btn')?.addEventListener('click', () => {
    void reviewCluster(cluster.clusterId, 'pending');
  });
}

function selectedDraft(): TaxonomyDraftRecord | null {
  return state.drafts.find(item => item.id === state.selectedDraftId) ?? null;
}

function renderDraftDetail() {
  const draft = selectedDraft();
  const panel = getElement<HTMLDivElement>('#taxonomy-draft-detail-panel');
  if (!panel) return;

  if (!draft) {
    panel.innerHTML = '<div class="text-muted">Selecciona un draft para ver su detalle.</div>';
    return;
  }

  const payload = payloadForDraft(draft);
  const diff = payload?.diff_summary;
  const currentRule = payload?.current_rule_snapshot;
  const proposedRule = payload?.proposed_rule_update;

  panel.innerHTML = `
    <div class="mb-3">
      <div class="d-flex gap-2 align-items-center flex-wrap">
        ${proposalBadge(draft.action_type)}
        ${
          draft.status === 'published'
            ? '<span class="badge bg-dark">Publicado</span>'
            : statusBadge(
                draft.status === 'applied'
                  ? 'approved'
                  : draft.status === 'rejected'
                    ? 'rejected'
                    : 'pending'
              )
        }
      </div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Dominio destino</div>
      <div>${escapeHtml(draft.target_domain_code ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Canónico propuesto</div>
      <div>${escapeHtml(draft.proposed_canonical_name ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Estrategia apply</div>
      <div>${escapeHtml(payload?.apply_strategy ?? 'pendiente')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Texto origen</div>
      <div>${escapeHtml(payload?.source_text ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Aliases propuestos</div>
      <div>${renderList(payload?.proposed_aliases)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Servicio canónico</div>
      <div><span class="text-muted">Actual:</span> ${escapeHtml(payload?.current_canonical_name ?? '—')}</div>
      <div><span class="text-muted">Draft:</span> ${escapeHtml(payload?.applied_canonical_name ?? draft.proposed_canonical_name ?? '—')}</div>
      <div><span class="text-muted">ID aplicado:</span> ${escapeHtml(payload?.applied_canonical_service_id ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Diff alias</div>
      <div><span class="text-muted">Actual:</span> ${escapeHtml(diff?.alias_before ?? '—')}</div>
      <div><span class="text-muted">Draft:</span> ${escapeHtml(diff?.alias_after ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Diff dimensiones</div>
      <div><span class="text-muted">Actual:</span> ${renderList(currentRule?.required_dimensions ?? diff?.required_dimensions_before ?? null)}</div>
      <div class="mt-1"><span class="text-muted">Draft:</span> ${renderList(proposedRule?.required_dimensions ?? diff?.required_dimensions_after ?? null)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Estado de publicación</div>
      <div>Versión: ${escapeHtml(
        payload?.published_version ? String(payload.published_version) : '—'
      )}</div>
      <div>Publicado: ${formatDate(payload?.published_at ?? null)}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Aprobado por</div>
      <div>${escapeHtml(draft.approved_by ?? '—')}</div>
    </div>
    <div class="mb-3">
      <div class="small text-muted">Aprobado el</div>
      <div>${formatDate(draft.approved_at)}</div>
    </div>
    <div class="d-flex gap-2 flex-wrap">
      <button
        type="button"
        class="btn btn-outline-primary btn-sm"
        id="taxonomy-apply-draft-btn"
        ${draft.status !== 'draft' ? 'disabled' : ''}
      >
        Aplicar draft
      </button>
    </div>
  `;

  getElement<HTMLButtonElement>('#taxonomy-apply-draft-btn')?.addEventListener('click', () => {
    void applyDraft(draft.id);
  });
}

function renderTable() {
  const body = getElement<HTMLTableSectionElement>('#taxonomy-table-body');
  const tableWrapper = getElement<HTMLDivElement>('#taxonomy-table-wrapper');
  const emptyBlock = getElement<HTMLDivElement>('#taxonomy-empty');
  if (!body || !tableWrapper || !emptyBlock) return;

  if (state.items.length === 0) {
    body.innerHTML = '';
    tableWrapper.style.display = 'none';
    emptyBlock.style.display = 'block';
    renderDetail();
    return;
  }

  emptyBlock.style.display = 'none';
  tableWrapper.style.display = 'block';
  body.innerHTML = state.items
    .map(
      item => `
      <tr data-taxonomy-id="${item.clusterId}" class="${
        item.clusterId === state.selectedId ? 'table-active' : ''
      }">
        <td>
          <div class="fw-semibold">${escapeHtml(
            item.representative.source_text ??
              item.proposedCanonicalName ??
              item.representative.normalized_text
          )}</div>
          <small class="text-muted">${escapeHtml(item.variants.join(' · '))}</small>
        </td>
        <td>${escapeHtml(item.proposedDomainCode ?? '—')}</td>
        <td>${proposalBadge(item.proposalType)}</td>
        <td>${statusBadge(item.reviewStatus)}</td>
        <td>${confidenceText(item.confidenceScore)}</td>
        <td>${item.memberCount}</td>
        <td>${item.totalOccurrences}</td>
        <td><small class="text-muted">${formatDate(item.lastSeenAt)}</small></td>
      </tr>
    `
    )
    .join('');

  body.querySelectorAll<HTMLTableRowElement>('tr[data-taxonomy-id]').forEach(row => {
    row.addEventListener('click', () => {
      state.selectedId = row.dataset.taxonomyId ?? null;
      renderTable();
      renderDetail();
    });
  });

  if (!state.selectedId && state.items[0]) {
    state.selectedId = state.items[0].clusterId;
    renderTable();
    renderDetail();
  }
}

function renderDrafts() {
  const body = getElement<HTMLTableSectionElement>('#taxonomy-drafts-table-body');
  const wrapper = getElement<HTMLDivElement>('#taxonomy-drafts-table-wrapper');
  const empty = getElement<HTMLDivElement>('#taxonomy-drafts-empty');
  if (!body || !wrapper || !empty) return;

  if (state.drafts.length === 0) {
    body.innerHTML = '';
    wrapper.style.display = 'none';
    empty.style.display = 'block';
    renderDraftDetail();
    return;
  }

  empty.style.display = 'none';
  wrapper.style.display = 'block';
  body.innerHTML = state.drafts
    .map(
      draft => `
      <tr data-draft-id="${draft.id}" class="${draft.id === state.selectedDraftId ? 'table-active' : ''}">
        <td>${escapeHtml(draft.proposed_canonical_name ?? '—')}</td>
        <td>${escapeHtml(draft.target_domain_code ?? '—')}</td>
        <td>${proposalBadge(draft.action_type)}</td>
        <td>${
          draft.status === 'published'
            ? '<span class="badge bg-dark">Publicado</span>'
            : draft.status === 'applied'
              ? '<span class="badge bg-success">Aplicado</span>'
              : draft.status === 'draft'
                ? '<span class="badge bg-warning text-dark">Borrador</span>'
                : '<span class="badge bg-danger">Rechazado</span>'
        }</td>
        <td><small class="text-muted">${formatDate(draft.approved_at)}</small></td>
      </tr>
    `
    )
    .join('');

  body.querySelectorAll<HTMLTableRowElement>('tr[data-draft-id]').forEach(row => {
    row.addEventListener('click', () => {
      state.selectedDraftId = row.dataset.draftId ?? null;
      renderDrafts();
      renderDraftDetail();
    });
  });

  if (!state.selectedDraftId && state.drafts[0]) {
    state.selectedDraftId = state.drafts[0].id;
    renderDrafts();
    renderDraftDetail();
  }
}

async function loadSuggestions() {
  setLoading(true);
  setFeedback('');
  try {
    const [overview, catalog, response] = await Promise.all([
      apiProveedores.obtenerTaxonomiaOverview(),
      apiProveedores.obtenerTaxonomiaCatalogo(),
      apiProveedores.obtenerTaxonomiaClusters({
        status: state.filter,
        limit: 100
      })
    ]);
    state.overview = overview;
    state.catalog = catalog;
    renderOverview();
    if (!state.catalog?.domains.some(item => item.code === state.selectedDomainCode)) {
      state.selectedDomainCode = state.catalog?.domains[0]?.code ?? null;
    }
    renderCatalogTable();
    renderCatalogDetail();
    state.items = response.clusters ?? [];
    if (!state.items.some(item => item.clusterId === state.selectedId)) {
      state.selectedId = state.items[0]?.clusterId ?? null;
    }
    renderTable();
    renderDetail();
    await loadDrafts();
  } catch (error) {
    console.error('Error cargando sugerencias de taxonomía:', error);
    state.overview = null;
    state.catalog = null;
    state.items = [];
    state.drafts = [];
    state.selectedDomainCode = null;
    state.selectedId = null;
    state.selectedDraftId = null;
    renderCatalogTable();
    renderCatalogDetail();
    renderTable();
    renderDetail();
    renderDrafts();
    renderDraftDetail();
    renderOverview();
    setFeedback('No se pudieron cargar las sugerencias de taxonomía.', 'error');
  } finally {
    setLoading(false);
  }
}

async function loadDrafts() {
  try {
    const response = await apiProveedores.obtenerTaxonomiaDrafts();
    state.drafts = response.items ?? [];
    if (!state.drafts.some(item => item.id === state.selectedDraftId)) {
      state.selectedDraftId = state.drafts[0]?.id ?? null;
    }
    renderDrafts();
    renderDraftDetail();
  } catch (error) {
    console.error('Error cargando drafts de taxonomía:', error);
    state.drafts = [];
    state.selectedDraftId = null;
    renderDrafts();
    renderDraftDetail();
  }
}

async function reviewCluster(id: string, reviewStatus: 'pending' | 'rejected') {
  state.actionInFlightId = id;
  setFeedback('');
  try {
    await apiProveedores.revisarTaxonomiaCluster(id, { reviewStatus });
    setFeedback(
      reviewStatus === 'rejected'
        ? 'Caso marcado como rechazado.'
        : 'Caso devuelto a pendiente.',
      'success'
    );
    await loadSuggestions();
  } catch (error) {
    console.error('Error revisando caso de taxonomía:', error);
    setFeedback('No se pudo actualizar el estado del caso.', 'error');
  } finally {
    state.actionInFlightId = null;
  }
}

async function approveCluster(id: string) {
  state.actionInFlightId = id;
  setFeedback('');
  try {
    await apiProveedores.aprobarTaxonomiaCluster(id, {});
    setFeedback('Caso aprobado y enviado a borrador.', 'success');
    await loadSuggestions();
  } catch (error) {
    console.error('Error aprobando caso de taxonomía:', error);
    setFeedback('No se pudo aprobar el caso hacia borrador.', 'error');
  } finally {
    state.actionInFlightId = null;
  }
}

async function applyDraft(id: string) {
  state.actionInFlightId = id;
  setFeedback('');
  try {
    await apiProveedores.aplicarTaxonomiaDraft(id);
    setFeedback('Draft aplicado. Quedó preparado para publicación.', 'success');
    await loadSuggestions();
  } catch (error) {
    console.error('Error aplicando draft:', error);
    setFeedback('No se pudo aplicar el draft.', 'error');
  } finally {
    state.actionInFlightId = null;
  }
}

async function publishDrafts() {
  setFeedback('');
  try {
    const result = await apiProveedores.publicarTaxonomiaDrafts();
    setFeedback(
      `Nueva versión publicada: v${result.version}. Cambios publicados: ${result.publishedCount}.`,
      'success'
    );
    await loadSuggestions();
  } catch (error) {
    console.error('Error publicando taxonomía:', error);
    const message =
      error instanceof Error && error.message
        ? error.message
        : 'No se pudo publicar la nueva versión de taxonomía.';
    setFeedback(message, 'error');
  }
}

function bindEvents() {
  getElement<HTMLButtonElement>('#taxonomy-refresh-btn')?.addEventListener('click', () => {
    void loadSuggestions();
  });

  getElement<HTMLSelectElement>('#taxonomy-status-filter')?.addEventListener('change', event => {
    const target = event.currentTarget as HTMLSelectElement;
    state.filter = target.value as SuggestionFilter;
    void loadSuggestions();
  });

  getElement<HTMLButtonElement>('#taxonomy-publish-btn')?.addEventListener('click', () => {
    void publishDrafts();
  });
}

function init() {
  bindEvents();
  renderDetail();
  void loadSuggestions();
}

export const TaxonomySuggestionsManager = {
  iniciar: init,
  recargar: loadSuggestions
};

export type TaxonomySuggestionsManagerModule = typeof TaxonomySuggestionsManager;
