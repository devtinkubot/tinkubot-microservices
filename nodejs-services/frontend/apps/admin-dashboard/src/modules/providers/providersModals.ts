import type { ProviderRecord, ProviderServiceReview } from "@tinkubot/api-client";
import { escaparHtml, normalizarClaveServicio } from "./providersFormatters";
import type { ModalInstance } from "./providersTypes";

type BootstrapModalConstructor = {
  getOrCreateInstance: (element: Element) => ModalInstance;
};

type WindowWithBootstrap = Window & {
  bootstrap?: {
    Modal?: BootstrapModalConstructor;
  };
};

function obtenerElemento<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

function obtenerBootstrapModal(): BootstrapModalConstructor | undefined {
  return (window as WindowWithBootstrap).bootstrap?.Modal;
}

export function obtenerModalRevision(): ModalInstance | null {
  const modalElement = document.getElementById("provider-review-modal");
  const modal = obtenerBootstrapModal();
  if (!modalElement || !modal) {
    return null;
  }
  return modal.getOrCreateInstance(modalElement);
}

export function obtenerModalRevisionServicio(): ModalInstance | null {
  const modalElement = document.getElementById("provider-service-review-modal");
  const modal = obtenerBootstrapModal();
  if (!modalElement || !modal) {
    return null;
  }
  return modal.getOrCreateInstance(modalElement);
}

export function mostrarErrorModal(mensaje?: string): void {
  const contenedor = obtenerElemento<HTMLDivElement>("#provider-review-error");
  if (!contenedor) return;
  if (mensaje) {
    contenedor.textContent = mensaje;
    contenedor.classList.remove("d-none");
  } else {
    contenedor.textContent = "";
    contenedor.classList.add("d-none");
  }
}

export function limpiarFormularioRevision(): void {
  mostrarErrorModal();
  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  if (estadoSelect) {
    estadoSelect.value = "";
  }
  const nombresTextarea = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-first-names",
  );
  if (nombresTextarea) {
    nombresTextarea.value = "";
  }
  const apellidosTextarea = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-last-names",
  );
  if (apellidosTextarea) {
    apellidosTextarea.value = "";
  }
  const cedulaTextarea = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-id-number",
  );
  if (cedulaTextarea) {
    cedulaTextarea.value = "";
  }
  const revisorInput = obtenerElemento<HTMLInputElement>(
    "#provider-reviewer-name",
  );
  if (revisorInput) {
    revisorInput.value = "";
  }
  const checklistDocs = obtenerElemento<HTMLInputElement>(
    "#provider-review-check-docs",
  );
  if (checklistDocs) {
    checklistDocs.checked = false;
  }
  const feedback = obtenerElemento<HTMLSpanElement>(
    "#provider-detail-copy-feedback",
  );
  if (feedback) {
    feedback.textContent = "";
  }
  const hiddenId = obtenerElemento<HTMLInputElement>(
    "#provider-review-provider-id",
  );
  if (hiddenId) {
    hiddenId.value = "";
  }
  const experienciaSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-profile-experience-range",
  );
  if (experienciaSelect) {
    experienciaSelect.value = "";
  }
  const serviciosList = obtenerElemento<HTMLDivElement>(
    "#provider-profile-services-list",
  );
  if (serviciosList) {
    serviciosList.innerHTML = "";
  }
}

export function limpiarFormularioRevisionServicio(): void {
  const reviewId = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-id",
  );
  const providerId = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-provider-id",
  );
  const domainCode = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-domain-code",
  );
  const categoryName = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-category-name",
  );
  const serviceName = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-service-name",
  );
  const serviceSummary = obtenerElemento<HTMLTextAreaElement>(
    "#provider-service-review-service-summary",
  );
  const createDomain = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-create-domain",
  );
  const context = obtenerElemento<HTMLDivElement>(
    "#provider-service-review-context",
  );
  const feedback = obtenerElemento<HTMLDivElement>(
    "#provider-service-review-error",
  );

  if (reviewId) reviewId.value = "";
  if (providerId) providerId.value = "";
  if (domainCode) domainCode.value = "";
  if (categoryName) categoryName.value = "";
  if (serviceName) serviceName.value = "";
  if (serviceSummary) serviceSummary.value = "";
  if (createDomain) createDomain.checked = false;
  if (context) context.innerHTML = "";
  if (feedback) {
    feedback.textContent = "";
    feedback.classList.add("d-none");
  }
}

export function cerrarModalRevision(): void {
  const modal = obtenerModalRevision();
  if (modal) {
    modal.hide();
  }
  limpiarFormularioRevision();
}

export function actualizarOpcionesResultadoRevision(
  esEditable: boolean,
): void {
  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  if (!estadoSelect) return;

  const opciones = [
    {
      value: "approved",
      label: esEditable ? "Completar perfil" : "Aprobar",
    },
    { value: "rejected", label: "Rechazar y resetear" },
  ] as const;

  estadoSelect.innerHTML = [
    '<option value="" selected disabled>Selecciona un resultado</option>',
    ...opciones.map(
      (opcion) => `<option value="${opcion.value}">${opcion.label}</option>`,
    ),
  ].join("");
  estadoSelect.value = "";
}

export function actualizarCopyRevision(esEditable: boolean): void {
  const tituloBasico = obtenerElemento<HTMLElement>(
    "#provider-basic-section-title",
  );
  const tituloRevision = obtenerElemento<HTMLElement>(
    "#provider-review-section-title",
  );
  const checklist = obtenerElemento<HTMLElement>(
    "#provider-review-check-docs-label",
  );
  const ayudaFooter = obtenerElemento<HTMLElement>(
    "#provider-review-footer-help",
  );

  if (tituloBasico) {
    tituloBasico.textContent = "Información personal";
  }
  if (tituloRevision) {
    tituloRevision.textContent = esEditable
      ? "Completar o resetear perfil profesional"
      : "Validación administrativa";
  }
  if (checklist) {
    checklist.textContent = esEditable
      ? "La identidad ya fue validada. Completa el perfil para aprobar o rechaza para reiniciar el registro."
      : "Confirmo que revisé la información, identidad y contacto del proveedor.";
  }
  if (ayudaFooter) {
    ayudaFooter.textContent = esEditable
      ? "Completa experiencia y servicios para mover al proveedor a Operativos, o recházalo para ejecutar un reset fuerte."
      : "Aprobar notificará el resultado por WhatsApp. Rechazar ejecutará un reset fuerte para que el proveedor vuelva a registrarse.";
  }
}

function obtenerServicioAsociadoAReview(
  proveedor: ProviderRecord | null,
  review: ProviderServiceReview,
): {
  domainCode?: string | null;
  categoryName?: string | null;
  serviceName?: string | null;
  serviceSummary?: string | null;
} | null {
  if (!proveedor || !Array.isArray(proveedor.servicesAudit)) {
    return null;
  }

  const claveReview = normalizarClaveServicio(
    review.serviceNameNormalized || review.serviceName || review.rawServiceText,
  );
  if (!claveReview) return null;

  return (
    proveedor.servicesAudit.find((item) => {
      const claveServicio = normalizarClaveServicio(
        item.serviceNameNormalized || item.serviceName || item.rawServiceText,
      );
      return claveServicio === claveReview;
    }) || null
  );
}

export function actualizarFormularioRevisionServicio(
  review: ProviderServiceReview,
  provider: ProviderRecord | null,
): void {
  const domainCode = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-domain-code",
  );
  const categoryName = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-category-name",
  );
  const serviceName = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-service-name",
  );
  const serviceSummary = obtenerElemento<HTMLTextAreaElement>(
    "#provider-service-review-service-summary",
  );
  const createDomain = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-create-domain",
  );
  const reviewId = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-id",
  );
  const providerId = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-provider-id",
  );
  const context = obtenerElemento<HTMLDivElement>(
    "#provider-service-review-context",
  );
  const title = obtenerElemento<HTMLElement>(
    "#provider-service-review-modal-title",
  );
  const servicio = obtenerServicioAsociadoAReview(provider, review);

  if (reviewId) reviewId.value = review.id;
  if (providerId) providerId.value = provider?.id || review.providerId || "";
  if (domainCode) {
    domainCode.value =
      review.suggestedDomainCode ||
      review.assignedDomainCode ||
      servicio?.domainCode ||
      "";
  }
  if (categoryName) {
    categoryName.value =
      review.proposedCategoryName ||
      review.assignedCategoryName ||
      servicio?.categoryName ||
      "";
  }
  if (serviceName) {
    serviceName.value =
      review.assignedServiceName ||
      review.serviceName ||
      servicio?.serviceName ||
      "";
  }
  if (serviceSummary) {
    serviceSummary.value =
      review.proposedServiceSummary ||
      review.assignedServiceSummary ||
      servicio?.serviceSummary ||
      "";
  }
  if (createDomain) {
    createDomain.checked = false;
  }
  if (title) {
    title.textContent = "Ajustar sugerencia de servicio";
  }
  if (context) {
    const resumenContexto = [
      review.rawServiceText
        ? `Texto original: ${escaparHtml(review.rawServiceText)}`
        : null,
      review.reviewReason
        ? `Motivo: ${escaparHtml(review.reviewReason)}`
        : null,
    ]
      .filter(Boolean)
      .map(
        (item) =>
          `<div class="provider-service-review-context-line">${item}</div>`,
      )
      .join("");
    context.innerHTML = resumenContexto;
  }
}
