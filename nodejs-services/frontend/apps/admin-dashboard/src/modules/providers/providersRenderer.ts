import type { ProviderRecord, ProviderServiceReview } from "@tinkubot/api-client";
import {
  construirUrlWhatsApp,
  escaparHtml,
  extraerPrimerNombre,
  formatearAntiguedadAprobacion,
  formatearFechaLarga,
  normalizarClaveServicio,
  normalizarPasoOnboarding,
  resolverAntiguedadOnboarding,
  resolverNombreVisibleOperativoProveedor,
  resolverNombreVisibleProveedor,
  resolverTelefonoVisibleOperativoProveedor,
  resolverTextoVisible,
} from "./providersFormatters";
import type { OnboardingColumn, ProviderBucket } from "./providersTypes";

const EXPERIENCE_RANGE_OPTIONS = [
  "Menos de 1 año",
  "1 a 3 años",
  "3 a 5 años",
  "5 a 10 años",
  "Más de 10 años",
];

const ONBOARDING_COLUMNS: OnboardingColumn[] = [
  { state: "onboarding_city", title: "Ciudad" },
  { state: "onboarding_dni_front_photo", title: "Cédula frontal" },
  { state: "onboarding_face_photo", title: "Foto de perfil" },
  { state: "onboarding_experience", title: "Experiencia" },
  { state: "onboarding_real_phone", title: "Teléfono real" },
  { state: "onboarding_specialty", title: "Servicios" },
];

function obtenerElemento<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

export function construirFilaServicioEditable(
  valor: string,
  indice: number,
): string {
  const placeholder = `Servicio ${indice + 1}`;
  return `
    <div class="input-group" data-profile-service-row>
      <input
        type="text"
        class="form-control"
        data-profile-service-input
        value="${escaparHtml(valor)}"
        placeholder="${escaparHtml(placeholder)}"
      />
      <button
        type="button"
        class="btn btn-outline-danger"
        data-profile-service-remove
      >
        <i class="fas fa-trash me-1"></i>
        Quitar
      </button>
    </div>
  `;
}

export function renderizarEditorServiciosProfesionales(
  servicios: string[],
): void {
  const contenedor = obtenerElemento<HTMLDivElement>(
    "#provider-profile-services-list",
  );
  if (!contenedor) return;

  const serviciosRender = servicios.length > 0 ? servicios : [""];
  contenedor.innerHTML = serviciosRender
    .map((valor, indice) => construirFilaServicioEditable(valor, indice))
    .join("");
}

export function renderizarOpcionesExperienciaProfesional(
  valorSeleccionado: string | null | undefined,
): void {
  const selector = obtenerElemento<HTMLSelectElement>(
    "#provider-profile-experience-range",
  );
  if (!selector) return;

  const seleccion = valorSeleccionado?.trim() || "";
  selector.innerHTML = [
    '<option value="" disabled>Sin definir</option>',
    ...EXPERIENCE_RANGE_OPTIONS.map(
      (option) =>
        `<option value="${escaparHtml(option)}">${escaparHtml(option)}</option>`,
    ),
  ].join("");
  selector.value = EXPERIENCE_RANGE_OPTIONS.includes(seleccion)
    ? seleccion
    : "";
}

export function obtenerEtiquetaEstadoListado(
  status?: ProviderRecord["status"] | null,
): string {
  switch (status) {
    case "rejected":
      return "Rechazado";
    case "approved":
      return "Aprobado";
    case "pending":
    default:
      return "Nuevo";
  }
}

export function obtenerClaseEstadoListado(
  status?: ProviderRecord["status"] | null,
): string {
  switch (status) {
    case "rejected":
      return "bg-danger";
    case "approved":
      return "bg-success";
    case "pending":
    default:
      return "bg-warning text-dark";
  }
}

export function actualizarEncabezadoBucket(
  bucketActivo: ProviderBucket,
): void {
  const titulo = obtenerElemento<HTMLElement>("#providers-title");
  const subtitulo = obtenerElemento<HTMLElement>("#providers-subtitle");
  const vacio = obtenerElemento<HTMLElement>("#providers-empty");
  const textoCarga =
    obtenerElemento<HTMLElement>("#providers-loading")?.querySelector("p");

  if (bucketActivo === "onboarding") {
    if (titulo) titulo.textContent = "Onboarding";
    if (subtitulo) {
      subtitulo.textContent =
        "Seguimiento por fase del alta de proveedores, sin saturar al administrativo.";
    }
    if (vacio) vacio.textContent = "No hay proveedores en onboarding.";
    if (textoCarga)
      textoCarga.textContent = "Obteniendo onboarding de proveedores...";
    return;
  }

  if (bucketActivo === "profile_incomplete") {
    if (titulo) titulo.textContent = "Incompletos";
    if (subtitulo) {
      subtitulo.textContent =
        "Proveedores aprobados o heredados que aún no quedan publicables. Aquí caen las irregularidades y casos por remediar.";
    }
    if (vacio) vacio.textContent = "No hay proveedores incompletos.";
    if (textoCarga)
      textoCarga.textContent = "Obteniendo proveedores incompletos...";
    return;
  }

  if (bucketActivo === "operativos") {
    if (titulo) titulo.textContent = "Operativos";
    if (subtitulo) {
      subtitulo.textContent =
        "Proveedores aprobados con perfil profesional completo y datos mínimos listos para operar.";
    }
    if (vacio) vacio.textContent = "No hay proveedores operativos.";
    if (textoCarga)
      textoCarga.textContent = "Obteniendo proveedores operativos...";
    return;
  }

  if (titulo) titulo.textContent = "Nuevos";
  if (subtitulo) {
    subtitulo.textContent = "Onboardings completos que ya esperan revisión.";
  }
  if (vacio) vacio.textContent = "No hay proveedores nuevos por revisar.";
  if (textoCarga) textoCarga.textContent = "Obteniendo proveedores nuevos...";
}

function construirFilaServicioPerfil(
  servicio: {
    serviceName?: string | null;
    serviceNameNormalized?: string | null;
    rawServiceText?: string | null;
    serviceSummary?: string | null;
    domainCode?: string | null;
    categoryName?: string | null;
    classificationConfidence?: number | null;
    requiresReview?: boolean | null;
  },
  indice: number,
  review?: ProviderServiceReview | null,
  providerIdSeleccionado?: string | null,
): string {
  const nombre =
    servicio.serviceName ||
    servicio.serviceNameNormalized ||
    "Servicio sin nombre";
  const textoCrudo = servicio.rawServiceText || nombre;
  const confianza =
    typeof servicio.classificationConfidence === "number" &&
    Number.isFinite(servicio.classificationConfidence)
      ? `${Math.round(servicio.classificationConfidence * 100)}%`
      : "—";
  const requiereRevision =
    Boolean(review) ||
    Boolean(servicio.requiresReview) ||
    (typeof servicio.classificationConfidence === "number" &&
      servicio.classificationConfidence < 0.7);
  const claseTarjeta = requiereRevision ? "provider-service-card--review" : "";
  const badgeEstado = requiereRevision
    ? '<span class="badge text-bg-warning">Pendiente</span>'
    : '<span class="badge text-bg-success">Claro</span>';
  const dominioActual = servicio.domainCode
    ? `<span class="provider-service-tag"><i class="fas fa-layer-group me-1"></i>${escaparHtml(
        servicio.domainCode,
      )}</span>`
    : '<span class="provider-service-tag text-muted">Sin dominio</span>';
  const categoriaActual = servicio.categoryName
    ? `<span class="provider-service-tag"><i class="fas fa-tags me-1"></i>${escaparHtml(
        servicio.categoryName,
      )}</span>`
    : '<span class="provider-service-tag text-muted">Sin categoría</span>';
  const resumen = servicio.serviceSummary
    ? `<div class="provider-service-raw mt-2">${escaparHtml(servicio.serviceSummary)}</div>`
    : "";
  const sugerencia = review
    ? `
      <div class="provider-service-suggestion mt-2">
        <div class="provider-service-suggestion-title">Sugerencia IA</div>
        <div class="provider-service-suggestion-grid">
          <div class="provider-service-suggestion-line">
            <strong>Dominio:</strong> ${escaparHtml(review.suggestedDomainCode || review.assignedDomainCode || "Sin sugerencia")}
          </div>
          <div class="provider-service-suggestion-line">
            <strong>Categoría:</strong> ${escaparHtml(review.proposedCategoryName || review.assignedCategoryName || "Sin sugerencia")}
          </div>
          ${
            review.reviewReason
              ? `<div class="provider-service-suggestion-line text-muted">${escaparHtml(review.reviewReason)}</div>`
              : ""
          }
        </div>
      </div>
    `
    : "";

  return `
    <tr class="${claseTarjeta}">
      <td>
        <div class="provider-service-name">${indice + 1}. ${escaparHtml(nombre)}</div>
        <div class="provider-service-raw">${escaparHtml(textoCrudo)}</div>
        ${review ? '<span class="badge text-bg-warning mt-2">Pendiente</span>' : badgeEstado}
      </td>
      <td>
        <div class="provider-service-meta">
          ${dominioActual}
          ${categoriaActual}
        </div>
      </td>
      <td>
        <span class="provider-service-tag">
          <i class="fas fa-shield-alt me-1"></i>Confianza ${escaparHtml(confianza)}
        </span>
        ${resumen}
      </td>
      <td>
        ${sugerencia}
        ${
          review
            ? `
          <div class="provider-service-actions mt-2">
            <button
              type="button"
              class="btn btn-primary btn-sm"
              data-service-review-action="accept"
              data-review-id="${escaparHtml(review.id)}"
              data-provider-id="${escaparHtml(providerIdSeleccionado || "")}"
            >
              <i class="fas fa-check me-1"></i>
              Aceptar
            </button>
            <button
              type="button"
              class="btn btn-outline-secondary btn-sm"
              data-service-review-action="edit"
              data-review-id="${escaparHtml(review.id)}"
              data-provider-id="${escaparHtml(providerIdSeleccionado || "")}"
            >
              <i class="fas fa-pen me-1"></i>
              Editar
            </button>
          </div>
        `
            : ""
        }
      </td>
    </tr>
  `;
}

function construirFilaReviewSinEmparejar(
  review: ProviderServiceReview,
  indice: number,
  providerIdSeleccionado?: string | null,
): string {
  const dominio =
    review.suggestedDomainCode || review.assignedDomainCode || "Sin dominio";
  const categoria =
    review.proposedCategoryName ||
    review.assignedCategoryName ||
    "Sin categoría";
  const resumen =
    review.proposedServiceSummary ||
    review.assignedServiceSummary ||
    review.serviceName ||
    "Sin resumen";
  return `
    <tr class="provider-service-card--review">
      <td>
        <div class="provider-service-name">${indice + 1}. ${escaparHtml(
          review.serviceName ||
            review.serviceNameNormalized ||
            "Sugerencia pendiente",
        )}</div>
        <div class="provider-service-raw">${escaparHtml(review.rawServiceText || "Sin texto original")}</div>
        <span class="badge text-bg-warning mt-2">Pendiente</span>
      </td>
      <td>
        <div class="provider-service-meta">
          <span class="provider-service-tag"><strong>Dominio:</strong>&nbsp;${escaparHtml(dominio)}</span>
          <span class="provider-service-tag"><strong>Categoría:</strong>&nbsp;${escaparHtml(categoria)}</span>
        </div>
      </td>
      <td>
        <span class="provider-service-tag"><strong>Resumen:</strong>&nbsp;${escaparHtml(resumen)}</span>
        ${
          review.reviewReason
            ? `<div class="provider-service-raw mt-2">${escaparHtml(review.reviewReason)}</div>`
            : ""
        }
      </td>
      <td>
        <div class="provider-service-actions">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            data-service-review-action="accept"
            data-review-id="${escaparHtml(review.id)}"
            data-provider-id="${escaparHtml(review.providerId || providerIdSeleccionado || "")}"
          >
            <i class="fas fa-check me-1"></i>
            Aceptar
          </button>
          <button
            type="button"
            class="btn btn-outline-secondary btn-sm"
            data-service-review-action="edit"
            data-review-id="${escaparHtml(review.id)}"
            data-provider-id="${escaparHtml(review.providerId || providerIdSeleccionado || "")}"
          >
            <i class="fas fa-pen me-1"></i>
            Editar
          </button>
        </div>
      </td>
    </tr>
  `;
}

export function renderizarFilaProveedorGeneral(
  proveedor: ProviderRecord,
): string {
  const { id, contactPhone, registeredAt, city } = proveedor;
  const nombreVisible = resolverNombreVisibleProveedor(proveedor);
  const telefonoPresentable = proveedor.contactPhone
    ? resolverTextoVisible(contactPhone)
    : null;

  const contactoMarkup = telefonoPresentable
    ? escaparHtml(telefonoPresentable)
    : '<span class="text-muted">Sin contacto</span>';

  const ubicacion = city
    ? escaparHtml(city)
    : '<span class="text-muted">Sin ciudad</span>';

  return `
    <tr data-provider-id="${escaparHtml(id)}">
      <td>
        <div class="fw-semibold">${escaparHtml(nombreVisible)}</div>
      </td>
      <td>${contactoMarkup}</td>
      <td>${ubicacion}</td>
      <td>
        <span class="text-muted small">
          ${escaparHtml(formatearFechaLarga(registeredAt))}
        </span>
      </td>
      <td class="text-end">
        <button
          type="button"
          class="btn btn-sm btn-primary"
          data-provider-action="review"
          data-provider-id="${escaparHtml(id)}"
        >
          <i class="fas fa-eye me-1"></i>
          Revisar
        </button>
      </td>
    </tr>
  `;
}

export function renderizarFilaProveedorOperativo(
  proveedor: ProviderRecord,
): string {
  const { id, registeredAt, city } = proveedor;
  const nombreVisible = resolverNombreVisibleOperativoProveedor(proveedor);
  const telefonoVisible = resolverTelefonoVisibleOperativoProveedor(proveedor);
  const estadoContacto = proveedor.contactStatus
    ? proveedor.contactStatus
    : null;

  const telefonoMarkup = telefonoVisible
    ? `<div class="text-muted small mt-1">${escaparHtml(telefonoVisible)}</div>`
    : '<div class="text-muted small mt-1">Sin teléfono visible</div>';

  const estadoContactoMarkup = estadoContacto
    ? `<span class="badge bg-light text-dark border">${escaparHtml(
        estadoContacto,
      )}</span>`
    : '<span class="text-muted">Sin estado</span>';

  const ubicacion = city
    ? escaparHtml(city)
    : '<span class="text-muted">Sin ciudad</span>';

  return `
    <tr data-provider-id="${escaparHtml(id)}">
      <td>
        <div class="fw-semibold">${escaparHtml(nombreVisible)}</div>
        ${telefonoMarkup}
      </td>
      <td>${estadoContactoMarkup}</td>
      <td>${ubicacion}</td>
      <td>
        <span class="text-muted small">
          ${escaparHtml(formatearFechaLarga(registeredAt))}
        </span>
      </td>
      <td class="text-end">
        <button
          type="button"
          class="btn btn-sm btn-primary"
          data-provider-action="review"
          data-provider-id="${escaparHtml(id)}"
        >
          <i class="fas fa-eye me-1"></i>
          Revisar
        </button>
      </td>
    </tr>
  `;
}

export function renderizarFilaPerfilProfesionalIncompleto(
  proveedor: ProviderRecord,
): string {
  const firstName = extraerPrimerNombre(
    resolverNombreVisibleProveedor(proveedor),
  );
  const ciudad = proveedor.city?.trim()
    ? escaparHtml(proveedor.city.trim())
    : '<span class="text-muted">Sin ciudad</span>';
  const antiguedad = formatearAntiguedadAprobacion(
    proveedor.approvedBasicAt ?? proveedor.registeredAt ?? null,
  );
  const ageMarkup = antiguedad
    ? `<span class="fw-semibold">${escaparHtml(antiguedad)}</span>`
    : '<span class="text-muted">Sin fecha de aprobación</span>';
  const whatsappUrl = construirUrlWhatsApp(
    proveedor.contactPhone || proveedor.realPhone || proveedor.phone,
  );
  const contactoMarkup = whatsappUrl
    ? `<a class="btn btn-sm btn-success" href="${escaparHtml(whatsappUrl)}" target="_blank" rel="noopener noreferrer" aria-label="Abrir WhatsApp con ${escaparHtml(firstName)}"><i class="fab fa-whatsapp me-1"></i>WhatsApp</a>`
    : `<button class="btn btn-sm btn-outline-secondary" type="button" disabled>Sin WhatsApp</button>`;

  return `
    <tr data-provider-id="${escaparHtml(proveedor.id)}">
      <td>
        <div class="fw-semibold">${escaparHtml(firstName)}</div>
      </td>
      <td>${ciudad}</td>
      <td>${ageMarkup}</td>
      <td>${contactoMarkup}</td>
      <td class="text-end">
        <button
          type="button"
          class="btn btn-sm btn-outline-primary"
          data-provider-action="review"
          data-provider-id="${escaparHtml(proveedor.id)}"
        >
          <i class="fas fa-eye me-1"></i>
          Ver detalle
        </button>
      </td>
    </tr>
  `;
}

export function renderizarTarjetaOnboarding(
  proveedor: ProviderRecord,
): string {
  const nombreVisible = resolverNombreVisibleProveedor(proveedor);
  const telefonoVisible = resolverTextoVisible(
    proveedor.contactPhone || proveedor.realPhone || proveedor.phone,
  );
  const antiguedad = resolverAntiguedadOnboarding(proveedor.registeredAt);
  const claseNivel =
    antiguedad.nivel === "critical"
      ? "critical"
      : antiguedad.nivel === "warning"
        ? "warning"
        : "fresh";
  const mostrarReset = antiguedad.nivel !== "fresh";
  return `
    <article class="providers-kanban-card providers-kanban-card--${claseNivel}">
      <div class="providers-kanban-card-top">
        <div class="providers-kanban-card-contact">
          <div class="providers-kanban-card-name">${escaparHtml(nombreVisible)}</div>
          ${
            telefonoVisible
              ? `<div class="providers-kanban-card-meta"><i class="fas fa-phone me-1"></i>${escaparHtml(telefonoVisible)}</div>`
              : ""
          }
        </div>
        ${
          antiguedad.etiqueta
            ? `<span class="providers-kanban-card-age providers-kanban-card-age--${claseNivel}">
                <i class="fas fa-clock me-1"></i>${escaparHtml(antiguedad.etiqueta)}
              </span>`
            : ""
        }
      </div>
      ${
        mostrarReset
          ? `<div class="providers-kanban-card-actions">
              <button
                type="button"
                class="btn btn-sm ${antiguedad.nivel === "critical" ? "btn-danger" : "btn-outline-warning"}"
                data-provider-action="reset"
                data-provider-id="${escaparHtml(proveedor.id)}"
              >
                <i class="fas fa-rotate-right me-1"></i>
                Reset
              </button>
            </div>`
          : ""
      }
    </article>
  `;
}

export function renderizarTableroOnboarding(
  proveedores: readonly ProviderRecord[],
): void {
  const wrapper = obtenerElemento<HTMLDivElement>("#providers-kanban-wrapper");
  const nav = obtenerElemento<HTMLDivElement>("#providers-kanban-nav");
  const board = obtenerElemento<HTMLDivElement>("#providers-kanban-board");
  const estadoVacio = obtenerElemento<HTMLDivElement>("#providers-empty");
  if (!wrapper || !nav || !board || !estadoVacio) {
    return;
  }

  const agrupados = new Map<string, ProviderRecord[]>();
  for (const proveedor of proveedores) {
    const paso = normalizarPasoOnboarding(proveedor);
    if (!paso) {
      continue;
    }
    if (!agrupados.has(paso)) {
      agrupados.set(paso, []);
    }
    agrupados.get(paso)?.push(proveedor);
  }

  const totalOnboarding = Array.from(agrupados.values()).reduce(
    (acumulado, lista) => acumulado + lista.length,
    0,
  );
  if (totalOnboarding === 0) {
    wrapper.style.display = "none";
    nav.innerHTML = "";
    board.innerHTML = "";
    estadoVacio.style.display = "block";
    return;
  }

  nav.innerHTML = ONBOARDING_COLUMNS.map(
    (columna) => `
      <button
        type="button"
        class="btn btn-outline-primary btn-sm"
        data-onboarding-jump="${escaparHtml(columna.state)}"
      >
        ${escaparHtml(columna.title)}
      </button>
    `,
  ).join("");

  board.innerHTML = ONBOARDING_COLUMNS.map((columna) => {
    const proveedoresColumna = agrupados.get(columna.state) ?? [];
    const contenido = proveedoresColumna.length
      ? proveedoresColumna
          .map((proveedor) => renderizarTarjetaOnboarding(proveedor))
          .join("")
      : '<div class="providers-kanban-empty">Sin proveedores en esta fase.</div>';
    return `
      <section
        class="providers-kanban-column"
        id="onboarding-column-${escaparHtml(columna.state)}"
        data-onboarding-column="${escaparHtml(columna.state)}"
      >
        <div class="providers-kanban-column-header">
          <div>
            <div class="providers-kanban-column-title">${escaparHtml(columna.title)}</div>
            <div class="providers-kanban-column-key">${escaparHtml(columna.state)}</div>
          </div>
          <span class="providers-kanban-column-count">${proveedoresColumna.length}</span>
        </div>
        <div class="providers-kanban-column-list">
          ${contenido}
        </div>
      </section>
    `;
  }).join("");

  estadoVacio.style.display = "none";
  wrapper.style.display = "block";
}

export function renderizarEncabezadoTabla(
  bucketActivo: ProviderBucket,
): void {
  const encabezado = obtenerElemento<HTMLTableSectionElement>(
    "#providers-table-head",
  );
  if (!encabezado) return;

  if (bucketActivo === "profile_incomplete") {
    encabezado.innerHTML = `
      <tr>
        <th>Proveedor</th>
        <th>Ciudad</th>
        <th>Antigüedad</th>
        <th>Contacto</th>
        <th class="text-end">Detalle</th>
      </tr>
    `;
    return;
  }

  encabezado.innerHTML = `
    <tr>
      <th>Nombre</th>
      <th>Contacto</th>
      <th>Ciudad</th>
      <th>Fecha de Registro</th>
      <th class="text-end">Revisión</th>
    </tr>
  `;
}

export function renderizarProveedores(
  bucketActivo: ProviderBucket,
  proveedores: readonly ProviderRecord[],
): void {
  const estadoVacio = obtenerElemento<HTMLDivElement>("#providers-empty");
  const contenedorTabla = obtenerElemento<HTMLDivElement>(
    "#providers-table-wrapper",
  );
  const contenedorKanban = obtenerElemento<HTMLDivElement>(
    "#providers-kanban-wrapper",
  );
  const cuerpoTabla = obtenerElemento<HTMLTableSectionElement>(
    "#providers-table-body",
  );

  if (!contenedorTabla || !cuerpoTabla || !estadoVacio) {
    return;
  }

  if (bucketActivo === "onboarding") {
    contenedorTabla.style.display = "none";
    cuerpoTabla.innerHTML = "";
    if (contenedorKanban) {
      contenedorKanban.style.display = "block";
    }
    if (proveedores.length === 0) {
      if (contenedorKanban) {
        contenedorKanban.style.display = "none";
      }
      estadoVacio.style.display = "block";
      return;
    }

    estadoVacio.style.display = "none";
    renderizarTableroOnboarding(proveedores);
    return;
  }

  if (contenedorKanban) {
    contenedorKanban.style.display = "none";
  }

  renderizarEncabezadoTabla(bucketActivo);

  if (proveedores.length === 0) {
    contenedorTabla.style.display = "none";
    cuerpoTabla.innerHTML = "";
    estadoVacio.style.display = "block";
    return;
  }

  estadoVacio.style.display = "none";
  contenedorTabla.style.display = "block";

  const filas = proveedores
    .map((proveedor) =>
      bucketActivo === "profile_incomplete"
        ? renderizarFilaPerfilProfesionalIncompleto(proveedor)
        : bucketActivo === "operativos"
          ? renderizarFilaProveedorOperativo(proveedor)
          : renderizarFilaProveedorGeneral(proveedor),
    )
    .join("");

  cuerpoTabla.innerHTML = filas;
}

export function prepararTablaServicioPerfil(
  serviciosDetalle: Array<{
    serviceName?: string | null;
    serviceNameNormalized?: string | null;
    rawServiceText?: string | null;
    serviceSummary?: string | null;
    domainCode?: string | null;
    categoryName?: string | null;
    classificationConfidence?: number | null;
    requiresReview?: boolean | null;
  }>,
  reviewsPendientes: ProviderServiceReview[],
  providerIdSeleccionado?: string | null,
): string {
  const reviewsUsadas = new Set<string>();
  const filasServicios = serviciosDetalle
    .map((item, index) => {
      const review = obtenerReviewServicioProveedor(item, reviewsPendientes);
      if (review?.id) {
        reviewsUsadas.add(review.id);
      }
      return construirFilaServicioPerfil(
        item,
        index,
        review,
        providerIdSeleccionado,
      );
    })
    .join("");
  const filasSinEmparejar = reviewsPendientes
    .filter((review) => !reviewsUsadas.has(review.id))
    .map((review, index) =>
      construirFilaReviewSinEmparejar(
        review,
        serviciosDetalle.length + index,
        providerIdSeleccionado,
      ),
    )
    .join("");

  return `
    <div class="table-responsive provider-service-table-wrap">
      <table class="table table-sm align-middle provider-service-table mb-0">
        <thead>
          <tr>
            <th>Servicio</th>
            <th>Dominio / categoría</th>
            <th>Confianza</th>
            <th class="text-end">Revisión</th>
          </tr>
        </thead>
        <tbody>
          ${filasServicios}
          ${filasSinEmparejar}
        </tbody>
      </table>
    </div>
  `;
}

function obtenerReviewServicioProveedor(
  servicio: {
    serviceName?: string | null;
    serviceNameNormalized?: string | null;
    rawServiceText?: string | null;
  },
  reviews: ProviderServiceReview[],
): ProviderServiceReview | null {
  const claves = [
    servicio.serviceNameNormalized,
    servicio.serviceName,
    servicio.rawServiceText,
  ]
    .map(normalizarClaveServicio)
    .filter((valor): valor is string => Boolean(valor));

  return (
    reviews.find((review) => {
      const reviewKey = normalizarClaveServicio(
        review.serviceNameNormalized ||
          review.serviceName ||
          review.rawServiceText,
      );
      return Boolean(reviewKey && claves.includes(reviewKey));
    }) || null
  );
}
