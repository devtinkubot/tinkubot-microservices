import {
  type ProviderProfessionalProfileUpdatePayload,
  type ProviderRecord,
  type ProviderServiceReview,
  type ProviderServiceReviewActionPayload,
} from "@tinkubot/api-client";
import { formatearTelefonoEcuador } from "../utils";
import {
  escaparHtml,
  formatearFechaLarga,
  limpiarTelefono,
  normalizarClaveServicio,
  normalizarListaServiciosEditable,
  normalizarTelefonoCopiable,
  resolverNombreVisibleSegunBucketActivo,
} from "./providersFormatters";
import {
  actualizarPerfilProfesional as actualizarPerfilProfesionalApi,
  aprobarReviewServicio,
  ejecutarAccionProveedor,
  obtenerDetalleProveedor,
  obtenerProveedoresPorBucket,
} from "./providersApi";
import {
  actualizarEncabezadoBucket,
  construirFilaServicioEditable,
  obtenerEtiquetaEstadoListado,
  prepararTablaServicioPerfil,
  renderizarEditorServiciosProfesionales,
  renderizarOpcionesExperienciaProfesional,
  renderizarPaginacion,
  renderizarProveedores,
} from "./providersRenderer";
import {
  actualizarCopyRevision,
  actualizarFormularioRevisionServicio,
  actualizarOpcionesResultadoRevision,
  cerrarModalRevision,
  limpiarFormularioRevision,
  limpiarFormularioRevisionServicio,
  mostrarErrorModal,
  obtenerModalRevision,
  obtenerModalRevisionServicio,
} from "./providersModals";
import {
  obtenerBucketActivo,
  obtenerPaginaOperativos,
  obtenerProveedores,
  obtenerProveedorSeleccionado,
  obtenerReviewSeleccionada,
  establecerBucketActivo,
  establecerPaginaOperativos,
  establecerEstadoCarga,
  establecerIdAccionEnProceso,
  establecerIdReviewEnProceso,
  establecerProveedores,
  establecerProveedorSeleccionado,
  establecerReviewSeleccionada,
} from "./providersState";
import type {
  AccionProveedorOpciones,
  OnboardingColumn,
  ProviderBucket,
} from "./providersTypes";

type ErrorConMensaje = Error & { message: string };

type TipoAviso = "success" | "error" | "info";

const ONBOARDING_COLUMNS: OnboardingColumn[] = [
  { state: "onboarding_city", title: "Ciudad" },
  { state: "onboarding_dni_front_photo", title: "Cédula frontal" },
  { state: "onboarding_face_photo", title: "Foto de perfil" },
  { state: "onboarding_experience", title: "Experiencia" },
  { state: "onboarding_real_phone", title: "Teléfono real" },
  { state: "onboarding_specialty", title: "Servicios" },
];

const EXPERIENCE_RANGE_OPTIONS = [
  "Menos de 1 año",
  "1 a 3 años",
  "3 a 5 años",
  "5 a 10 años",
  "Más de 10 años",
];

function extraerMensajeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (
    error &&
    typeof error === "object" &&
    "message" in error &&
    typeof (error as ErrorConMensaje).message === "string"
  ) {
    return (error as ErrorConMensaje).message;
  }
  return "Ocurrió un error al procesar la solicitud del proveedor.";
}

function obtenerElemento<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

function obtenerEtiquetaContactoOperativo(proveedor: ProviderRecord): string {
  switch (proveedor.contactStatus) {
    case "lid_with_real_phone":
      return "LID con número real confirmado";
    case "lid_missing_real_phone":
      return "LID sin número real";
    case "real_phone_available":
      return "Número real disponible";
    default:
      return "Solo teléfono base";
  }
}

function esPerfilProfesionalEditable(
  proveedor: ProviderRecord | null = obtenerProveedorSeleccionado(),
): boolean {
  if (obtenerBucketActivo() !== "profile_incomplete" || !proveedor) {
    return false;
  }

  return (
    proveedor.status === "approved" &&
    !tienePerfilProfesionalCompleto(proveedor)
  );
}

function tienePerfilProfesionalCompleto(
  proveedor: ProviderRecord | null | undefined,
): boolean {
  if (!proveedor) {
    return false;
  }

  const serviciosValidos = normalizarListaServiciosEditable(
    proveedor.servicesList,
  );
  const experiencia = proveedor.experienceRange?.trim();
  return Boolean(experiencia && serviciosValidos.length >= 1);
}

function obtenerValoresServiciosProfesionales(): string[] {
  const contenedor = obtenerElemento<HTMLDivElement>(
    "#provider-profile-services-list",
  );
  if (!contenedor) {
    return [];
  }

  return Array.from(
    contenedor.querySelectorAll<HTMLInputElement>(
      "[data-profile-service-input]",
    ),
  )
    .map((input) => input.value.trim())
    .filter((valor) => valor.length > 0);
}

function agregarFilaServicioProfesional(valor = ""): void {
  const contenedor = obtenerElemento<HTMLDivElement>(
    "#provider-profile-services-list",
  );
  if (!contenedor) return;

  const indice = contenedor.querySelectorAll(
    "[data-profile-service-row]",
  ).length;
  const wrapper = document.createElement("div");
  wrapper.innerHTML = construirFilaServicioEditable(valor, indice).trim();
  const fila = wrapper.firstElementChild;
  if (fila) {
    contenedor.appendChild(fila);
  }
}

function manejarAccionesEditorServiciosProfesionales(evento: Event): void {
  const objetivo = evento.target as HTMLElement;
  const botonEliminar = objetivo.closest<HTMLButtonElement>(
    "[data-profile-service-remove]",
  );
  if (!botonEliminar) return;

  const contenedor = obtenerElemento<HTMLDivElement>(
    "#provider-profile-services-list",
  );
  if (!contenedor) return;

  const filas = Array.from(
    contenedor.querySelectorAll<HTMLElement>("[data-profile-service-row]"),
  );
  const fila = botonEliminar.closest<HTMLElement>("[data-profile-service-row]");
  if (!fila) return;

  if (filas.length <= 1) {
    const input = fila.querySelector<HTMLInputElement>(
      "[data-profile-service-input]",
    );
    if (input) {
      input.value = "";
      input.focus();
    }
    return;
  }

  fila.remove();
}

function mostrarAviso(mensaje: string, tipo: TipoAviso = "info"): void {
  const contenedorAvisos = obtenerElemento<HTMLDivElement>(
    "#providers-feedback",
  );
  if (!contenedorAvisos) return;

  if (!mensaje) {
    contenedorAvisos.style.display = "none";
    contenedorAvisos.textContent = "";
    contenedorAvisos.className = "alert";
    return;
  }

  const claseAviso =
    tipo === "success"
      ? "alert-success"
      : tipo === "error"
        ? "alert-danger"
        : "alert-info";
  contenedorAvisos.className = `alert ${claseAviso}`;
  contenedorAvisos.textContent = mensaje;
  contenedorAvisos.style.display = "block";
}

function establecerTexto(
  selector: string,
  valor: string | null | undefined,
  opciones: { fallback?: string; emptyClass?: string } = {},
): void {
  const elemento = obtenerElemento<HTMLElement>(selector);
  if (!elemento) return;
  const { fallback = "—", emptyClass = "text-muted" } = opciones;

  if (valor && valor.trim().length > 0) {
    elemento.textContent = valor.trim();
    elemento.classList.remove(emptyClass);
  } else {
    elemento.textContent = fallback;
    elemento.classList.add(emptyClass);
  }
}

function sincronizarEstadoCarga(estaCargando: boolean): void {
  establecerEstadoCarga(estaCargando);
  const contenedorCarga = obtenerElemento<HTMLDivElement>("#providers-loading");
  if (contenedorCarga) {
    contenedorCarga.style.display = estaCargando ? "block" : "none";
  }

  const botonRefrescar = obtenerElemento<HTMLButtonElement>(
    "#providers-refresh-btn",
  );
  if (botonRefrescar) {
    botonRefrescar.disabled = estaCargando;
    const spinner = botonRefrescar.querySelector(".loading-spinner");
    if (spinner instanceof HTMLElement) {
      spinner.style.display = estaCargando ? "inline-block" : "none";
    }
  }
}

function actualizarCertificados(proveedor: ProviderRecord): void {
  const contenedor = obtenerElemento<HTMLDivElement>(
    "#provider-detail-certificates",
  );
  const placeholder = obtenerElemento<HTMLDivElement>(
    "#provider-detail-certificates-empty",
  );
  if (!contenedor || !placeholder) return;

  const certificados = Array.isArray(proveedor.certificates)
    ? proveedor.certificates
    : [];
  const items = certificados
    .filter(
      (item) =>
        typeof item.fileUrl === "string" && item.fileUrl.trim().length > 0,
    )
    .map((item, index) => ({
      url: item.fileUrl.trim(),
      etiqueta: `Certificado ${index + 1}`,
    }));

  if (items.length === 0) {
    contenedor.innerHTML = "";
    placeholder.style.display = "block";
    return;
  }

  const tarjetas = items
    .map(
      (item) => `
        <div class="col-md-4">
          <div class="provider-document-card">
            <div class="provider-document-thumb">
              <a href="${escaparHtml(item.url)}" target="_blank" rel="noopener noreferrer">
                <img src="${escaparHtml(
                  item.url,
                )}" alt="${escaparHtml(item.etiqueta)}" loading="lazy"
                     onerror="this.onerror=null; this.src='data:image/svg+xml;base64,${btoa('<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"100\" height=\"100\" viewBox=\"0 0 100 100\"><rect width=\"100\" height=\"100\" fill=\"#f8f9fa\"/><text x=\"50\" y=\"50\" text-anchor=\"middle\" dy=\".3em\" fill=\"#6c757d\" font-family=\"Arial\" font-size=\"12\">Archivo</text></svg>')}; this.style.background='#f8f9fa'; this.style.border='1px solid #dee2e6';" />
              </a>
            </div>
            <p class="provider-document-label">${escaparHtml(item.etiqueta)}</p>
          </div>
        </div>
      `,
    )
    .join("");

  contenedor.innerHTML = tarjetas;
  placeholder.style.display = "none";
}

function actualizarContacto(proveedor: ProviderRecord): void {
  const telefono =
    proveedor.contactPhone ?? proveedor.realPhone ?? proveedor.phone ?? null;
  const realPhone = proveedor.realPhone ?? null;
  const telefonoPresentable = formatearTelefonoEcuador(telefono);
  const realPhonePresentable = formatearTelefonoEcuador(realPhone);
  const nombre = resolverNombreVisibleSegunBucketActivo(
    proveedor,
    obtenerBucketActivo(),
  );
  const estadoContacto = obtenerEtiquetaContactoOperativo(proveedor);

  establecerTexto("#provider-detail-phone", telefonoPresentable, {
    fallback: "Sin número",
  });
  establecerTexto("#provider-detail-real-phone", realPhonePresentable, {
    fallback: "Sin número real",
  });
  establecerTexto("#provider-detail-contact-status", estadoContacto);
  establecerTexto("#provider-detail-contact-name", nombre);

  const telefonoBtn = obtenerElemento<HTMLButtonElement>(
    "#provider-detail-copy-phone",
  );
  if (telefonoBtn) {
    if (telefono) {
      telefonoBtn.dataset.phone =
        normalizarTelefonoCopiable(telefono) ?? telefono;
      telefonoBtn.disabled = false;
    } else {
      delete telefonoBtn.dataset.phone;
      telefonoBtn.disabled = true;
    }
  }

  const enlaceWhatsapp = obtenerElemento<HTMLAnchorElement>(
    "#provider-detail-open-whatsapp",
  );
  if (enlaceWhatsapp) {
    if (telefono) {
      const telefonoE164 = telefono.replace(/[^\d+]/g, "");
      enlaceWhatsapp.href = `https://wa.me/${telefonoE164}`;
      enlaceWhatsapp.style.display = "inline-flex";
    } else {
      enlaceWhatsapp.style.display = "none";
    }
  }
}

function actualizarFotosIdentidad(proveedor: ProviderRecord): void {
  const contenedor = obtenerElemento<HTMLDivElement>(
    "#provider-detail-identity-photos",
  );
  const placeholder = obtenerElemento<HTMLDivElement>(
    "#provider-detail-identity-photos-empty",
  );
  if (!contenedor || !placeholder) return;

  const fotos = [
    {
      url: proveedor.documents?.dniFront ?? null,
      etiqueta: "Cédula frontal",
    },
    {
      url: proveedor.documents?.face ?? null,
      etiqueta: "Foto de perfil",
    },
  ];

  const tieneImagenes = fotos.some((foto) => Boolean(foto.url));
  if (!tieneImagenes) {
    contenedor.innerHTML = "";
    placeholder.style.display = "block";
    return;
  }

  const tarjetas = fotos
    .map(
      (foto) => `
        <div class="col-md-6">
          <div class="provider-document-card">
            <div class="provider-document-thumb">
              ${
                foto.url
                  ? `<a href="${escaparHtml(foto.url)}" target="_blank" rel="noopener noreferrer">
                      <img
                        src="${escaparHtml(foto.url)}"
                        alt="${escaparHtml(foto.etiqueta)}"
                        loading="lazy"
                      />
                    </a>`
                  : `<div class="d-flex align-items-center justify-content-center h-100"><span class="text-muted small">Sin imagen</span></div>`
              }
            </div>
            <p class="provider-document-label">${escaparHtml(foto.etiqueta)}</p>
          </div>
        </div>
      `,
    )
    .join("");

  contenedor.innerHTML = tarjetas;
  placeholder.style.display = "none";
}

function actualizarCamposIdentidad(proveedor: ProviderRecord): void {
  const nombres = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-first-names",
  );
  const apellidos = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-last-names",
  );
  const cedula = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-id-number",
  );

  if (nombres) {
    nombres.value = proveedor.documentFirstNames ?? "";
  }
  if (apellidos) {
    apellidos.value = proveedor.documentLastNames ?? "";
  }
  if (cedula) {
    cedula.value = proveedor.documentIdNumber ?? "";
  }
}

function actualizarPerfilProfesional(proveedor: ProviderRecord): void {
  const servicios = obtenerElemento<HTMLDivElement>(
    "#provider-detail-services",
  );
  const experiencia = obtenerElemento<HTMLElement>(
    "#provider-detail-experience",
  );
  const redSocial = obtenerElemento<HTMLElement>(
    "#provider-detail-social-media",
  );
  const serviciosDetalle = Array.isArray(proveedor.servicesAudit)
    ? proveedor.servicesAudit.filter(
        (item) =>
          typeof item?.serviceName === "string" &&
          item.serviceName.trim().length > 0,
      )
    : [];
  const reviewsPendientes = Array.isArray(proveedor.serviceReviews)
    ? proveedor.serviceReviews.filter(
        (item) => (item.reviewStatus || "").trim().toLowerCase() === "pending",
      )
    : [];
  const experienciaValor = proveedor.experienceRange?.trim() || "Sin definir";
  const etiquetasRedes = [
    proveedor.facebookUsername,
    proveedor.instagramUsername,
  ]
    .filter(
      (item): item is string =>
        typeof item === "string" && item.trim().length > 0,
    )
    .map((item) => `@${item.trim().replace(/^@+/, "")}`);
  const etiquetaRedSocial =
    etiquetasRedes.length > 0 ? etiquetasRedes.join(" · ") : null;

  if (servicios) {
    if (serviciosDetalle.length > 0 || reviewsPendientes.length > 0) {
      servicios.innerHTML = prepararTablaServicioPerfil(
        serviciosDetalle,
        reviewsPendientes,
        obtenerProveedorSeleccionado()?.id,
      );
      servicios.classList.remove("text-muted");
    } else {
      servicios.innerHTML =
        '<span class="provider-service-empty">Sin servicios registrados.</span>';
      servicios.classList.add("text-muted");
    }
  }

  if (experiencia) {
    establecerTexto("#provider-detail-experience", experienciaValor, {
      fallback: "Sin experiencia registrada",
    });
  }

  if (redSocial) {
    if (etiquetaRedSocial) {
      redSocial.innerHTML = escaparHtml(etiquetaRedSocial);
      redSocial.classList.remove("text-muted");
    } else {
      redSocial.textContent = "Sin red social registrada";
      redSocial.classList.add("text-muted");
    }
  }

  actualizarFormularioPerfilProfesional(proveedor);
}

function actualizarFormularioPerfilProfesional(proveedor: ProviderRecord): void {
  const esEditable = esPerfilProfesionalEditable(proveedor);
  const seccionIdentidad = obtenerElemento<HTMLElement>(
    "#provider-identity-edit-section",
  );
  const seccionCompletar = obtenerElemento<HTMLElement>(
    "#provider-profile-completion-section",
  );
  const seccionRevision = document.querySelector<HTMLElement>(
    "#provider-review-controls-section",
  );
  const botonEnviar = obtenerElemento<HTMLButtonElement>(
    "#provider-review-submit-btn",
  );
  const tituloRevision = obtenerElemento<HTMLElement>(
    "#provider-review-section-title",
  );
  const ayudaFooter = obtenerElemento<HTMLElement>(
    "#provider-review-footer-help",
  );
  const checklistLabel = obtenerElemento<HTMLElement>(
    "#provider-review-check-docs-label",
  );

  if (seccionIdentidad) {
    seccionIdentidad.style.display = esEditable ? "none" : "block";
  }
  if (seccionCompletar) {
    seccionCompletar.style.display = esEditable ? "block" : "none";
  }
  if (seccionRevision) {
    seccionRevision.style.display = esEditable ? "none" : "block";
  }
  if (botonEnviar) {
    botonEnviar.innerHTML = esEditable
      ? '<i class="fas fa-paper-plane me-1"></i> Ejecutar resultado'
      : '<i class="fas fa-paper-plane me-1"></i> Guardar y notificar';
    botonEnviar.classList.toggle("btn-primary", !esEditable);
    botonEnviar.classList.toggle("btn-success", esEditable);
  }
  if (tituloRevision) {
    tituloRevision.textContent = esEditable
      ? "Completar o resetear perfil profesional"
      : "Revisión administrativa del onboarding";
  }
  if (ayudaFooter) {
    ayudaFooter.textContent = esEditable
      ? "Completa experiencia y servicios para mover al proveedor a Operativos, o recházalo para ejecutar un reset fuerte."
      : "Aprobar notificará el resultado por WhatsApp. Rechazar ejecutará un reset fuerte para que el proveedor vuelva a registrarse.";
  }
  if (checklistLabel && esEditable) {
    checklistLabel.textContent =
      "La identidad ya fue validada. Completa el perfil para aprobar o rechaza para reiniciar el registro.";
  }

  if (esEditable) {
    renderizarOpcionesExperienciaProfesional(proveedor.experienceRange);
    renderizarEditorServiciosProfesionales(
      normalizarListaServiciosEditable(proveedor.servicesList),
    );
  }
}

function actualizarVistaOperativo(_proveedor: ProviderRecord): void {
  const esOperativo = obtenerBucketActivo() === "operativos";
  const esEditable = esPerfilProfesionalEditable(_proveedor);
  const seccionRevision = document.querySelector<HTMLElement>(
    ".provider-review-form",
  );
  const botonEnviar = obtenerElemento<HTMLButtonElement>(
    "#provider-review-submit-btn",
  );
  const ayudaFooter = obtenerElemento<HTMLElement>(
    "#provider-review-footer-help",
  );
  const tituloRevision = obtenerElemento<HTMLElement>(
    "#provider-review-section-title",
  );
  const checkboxDocs = obtenerElemento<HTMLInputElement>(
    "#provider-review-check-docs",
  );
  const selectorEstado = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  const inputRevisor = obtenerElemento<HTMLInputElement>(
    "#provider-reviewer-name",
  );
  const inputNombres = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-first-names",
  );
  const inputApellidos = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-last-names",
  );
  const inputCedula = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-id-number",
  );

  if (seccionRevision) {
    seccionRevision.style.display = esOperativo ? "none" : "block";
  }
  if (botonEnviar) {
    botonEnviar.style.display = esOperativo ? "none" : "";
    botonEnviar.innerHTML = esEditable
      ? '<i class="fas fa-paper-plane me-1"></i> Ejecutar resultado'
      : '<i class="fas fa-paper-plane me-1"></i> Guardar y notificar';
  }
  if (ayudaFooter) {
    ayudaFooter.textContent = esEditable
      ? "Completa experiencia y servicios para mover al proveedor a Operativos, o recházalo para ejecutar un reset fuerte."
      : esOperativo
        ? "Detalle operativo de solo lectura."
        : "Aprobar notificará el resultado por WhatsApp. Rechazar ejecutará un reset fuerte para que el proveedor vuelva a registrarse.";
  }
  if (tituloRevision) {
    tituloRevision.textContent = esEditable
      ? "Completar o resetear perfil profesional"
      : esOperativo
        ? "Detalle operativo"
        : "Revisión administrativa del onboarding";
  }

  if (checkboxDocs) {
    checkboxDocs.disabled = esOperativo || esEditable;
    checkboxDocs.checked = esEditable;
  }
  if (selectorEstado) {
    selectorEstado.disabled = esOperativo;
  }
  if (inputRevisor) {
    inputRevisor.disabled = esOperativo;
  }
  [inputNombres, inputApellidos, inputCedula].forEach((elemento) => {
    if (elemento) {
      elemento.disabled = esOperativo || esEditable;
    }
  });
}

function actualizarBadgeEstado(status: ProviderRecord["status"]): void {
  const badge = obtenerElemento<HTMLSpanElement>(
    "#provider-detail-status-badge",
  );
  if (!badge) return;

  badge.classList.remove(
    "bg-warning",
    "bg-success",
    "bg-danger",
    "bg-secondary",
    "bg-info",
    "text-dark",
  );

  switch (status) {
    case "approved":
      badge.classList.add("bg-success");
      badge.textContent = "Proveedor aprobado";
      break;
    case "rejected":
      badge.classList.add("bg-danger");
      badge.textContent = "Rechazado";
      break;
    default:
      badge.classList.add("bg-warning", "text-dark");
      badge.textContent = "Pendiente";
      break;
  }
}

function actualizarDetalleProveedor(proveedor: ProviderRecord): void {
  establecerTexto(
    "#provider-detail-name",
    resolverNombreVisibleSegunBucketActivo(proveedor, obtenerBucketActivo()),
  );
  actualizarBadgeEstado(proveedor.status);
  establecerTexto(
    "#provider-detail-status-text",
    obtenerEtiquetaEstadoListado(proveedor.status),
  );
  establecerTexto(
    "#provider-detail-registered",
    formatearFechaLarga(proveedor.registeredAt),
  );
  establecerTexto(
    "#provider-detail-stage",
    proveedor.status === "approved"
      ? proveedor.onboardingComplete
        ? "Proveedor operativo"
        : "Proveedor aprobado pendiente de completar"
      : "Onboarding básico",
  );

  const ubicacion =
    proveedor.city && proveedor.province
      ? `${proveedor.city}, ${proveedor.province}`
      : (proveedor.city ?? proveedor.province ?? null);
  establecerTexto("#provider-detail-location", ubicacion, {
    fallback: "Ubicación pendiente",
  });

  establecerTexto(
    "#provider-detail-consent",
    proveedor.hasConsent ? "Consentimiento registrado" : "Sin consentimiento",
    { fallback: "Sin datos" },
  );

  establecerTexto(
    "#provider-detail-verifier",
    proveedor.verificationReviewer
      ? `${proveedor.verificationReviewer} · ${formatearFechaLarga(proveedor.verificationReviewedAt)}`
      : null,
    { fallback: "Pendiente de revisión" },
  );

  actualizarContacto(proveedor);
  actualizarPerfilProfesional(proveedor);
  actualizarFotosIdentidad(proveedor);
  actualizarCertificados(proveedor);
  actualizarCamposIdentidad(proveedor);
  actualizarCopyRevision(esPerfilProfesionalEditable(proveedor));
  actualizarOpcionesResultadoRevision(esPerfilProfesionalEditable(proveedor));
  actualizarVistaOperativo(proveedor);

  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  if (estadoSelect) {
    estadoSelect.value = "";
  }

  const hiddenId = obtenerElemento<HTMLInputElement>(
    "#provider-review-provider-id",
  );
  if (hiddenId) {
    hiddenId.value = proveedor.id;
  }
}

function establecerAccionEnProceso(proveedorId: string | null): void {
  establecerIdAccionEnProceso(proveedorId);

  const fila = proveedorId
    ? obtenerElemento<HTMLTableRowElement>(
        `tr[data-provider-id="${proveedorId}"]`,
      )
    : null;

  if (fila) {
    const boton = fila.querySelector<HTMLButtonElement>(
      '[data-provider-action="review"]',
    );
    if (boton) {
      boton.disabled = Boolean(proveedorId);
    }
  }

  const botonEnviar = obtenerElemento<HTMLButtonElement>(
    "#provider-review-submit-btn",
  );
  const indicadorProceso = obtenerElemento<HTMLSpanElement>(
    "#provider-review-processing",
  );

  if (botonEnviar) {
    botonEnviar.disabled = Boolean(proveedorId);
  }

  if (indicadorProceso) {
    indicadorProceso.style.display = proveedorId ? "inline-flex" : "none";
  }
}

export async function cargarProveedoresBucket(): Promise<void> {
  sincronizarEstadoCarga(true);
  mostrarAviso("");

  try {
    const proveedores =
      await obtenerProveedoresPorBucket(obtenerBucketActivo());
    establecerProveedores(proveedores);
    renderizarProveedores(obtenerBucketActivo(), obtenerProveedores(), obtenerPaginaOperativos());
  } catch (error) {
    console.error("Error al cargar proveedores:", error);
    mostrarAviso(
      error instanceof Error
        ? error.message
        : "No se pudo cargar la lista de proveedores.",
      "error",
    );
    establecerProveedores([]);
    renderizarProveedores(obtenerBucketActivo(), obtenerProveedores(), obtenerPaginaOperativos());
  } finally {
    sincronizarEstadoCarga(false);
  }
}

async function cargarDetalleProveedorSeleccionado(
  proveedorId: string,
): Promise<void> {
  try {
    const detalle = await obtenerDetalleProveedor(proveedorId);
    if (obtenerProveedorSeleccionado()?.id === proveedorId && detalle) {
      establecerProveedorSeleccionado(detalle);
      actualizarDetalleProveedor(detalle);
      if (obtenerReviewSeleccionada()) {
        const reviewActualizada = Array.isArray(detalle.serviceReviews)
          ? (detalle.serviceReviews.find(
              (item) => item.id === obtenerReviewSeleccionada()?.id,
            ) ?? null)
          : null;
        if (reviewActualizada) {
          establecerReviewSeleccionada(reviewActualizada);
        }
      }
    }
  } catch (error) {
    console.error("No se pudo recargar el detalle del proveedor:", error);
  }
}

async function guardarPerfilProfesionalCompletado(
  proveedor: ProviderRecord,
): Promise<void> {
  const experienciaSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-profile-experience-range",
  );
  const experienciaSeleccionada = experienciaSelect?.value.trim() ?? "";
  const servicios = obtenerValoresServiciosProfesionales();

  if (!experienciaSeleccionada) {
    mostrarErrorModal("Selecciona un rango de experiencia antes de guardar.");
    experienciaSelect?.focus();
    return;
  }

  if (servicios.length === 0) {
    mostrarErrorModal("Agrega al menos un servicio antes de guardar.");
    const primerServicio = obtenerElemento<HTMLInputElement>(
      "[data-profile-service-input]",
    );
    primerServicio?.focus();
    return;
  }

  const payload: ProviderProfessionalProfileUpdatePayload = {
    services: servicios,
    experienceRange: experienciaSeleccionada,
    facebookUsername: proveedor.facebookUsername?.trim() || undefined,
    instagramUsername: proveedor.instagramUsername?.trim() || undefined,
  };

  const respuesta = await actualizarPerfilProfesionalApi(proveedor.id, payload);

  if (!respuesta.ok) {
    throw new Error(
      respuesta.errorReason ??
        "No se pudo actualizar el perfil profesional del proveedor.",
    );
  }

  mostrarAviso(
    respuesta.message ?? "Perfil profesional actualizado correctamente.",
    "success",
  );
  cerrarModalRevision();
  establecerProveedorSeleccionado(null);
  establecerReviewSeleccionada(null);
  await cargarProveedoresBucket();
}

async function abrirModalRevision(proveedorId: string): Promise<void> {
  const proveedor = obtenerProveedores().find((item) => item.id === proveedorId);
  if (!proveedor) {
    mostrarAviso(
      "No se encontró la información del proveedor seleccionado.",
      "error",
    );
    return;
  }

  establecerProveedorSeleccionado(proveedor);
  actualizarDetalleProveedor(proveedor);
  mostrarErrorModal();

  const modal = obtenerModalRevision();
  if (modal) {
    modal.show();
  }

  await cargarDetalleProveedorSeleccionado(proveedorId);
}

async function ejecutarAccionSobreProveedor(
  proveedorId: string,
  accion: "review" | "reset",
  opciones: AccionProveedorOpciones = {},
): Promise<void> {
  establecerAccionEnProceso(proveedorId);
  mostrarErrorModal();

  try {
    const ejecutarReset = accion === "reset" || opciones.status === "rejected";

    if (ejecutarReset) {
      const confirmado = window.confirm(
        opciones.status === "rejected"
          ? "Este rechazo ejecutará un reset fuerte. Se eliminará el avance actual del proveedor y deberá registrarse nuevamente. ¿Deseas continuar?"
          : "¿Quieres reiniciar la operación activa de este proveedor? Se eliminará su avance actual y podrá registrarse nuevamente.",
      );
      if (!confirmado) {
        return;
      }

      const respuesta = await ejecutarAccionProveedor(proveedorId, "reset", {
        ...opciones,
        status: "rejected",
      });
      if (!("success" in respuesta) || !respuesta.success) {
        throw new Error(
          ("message" in respuesta ? respuesta.message : undefined) ??
            "No se pudo reiniciar el onboarding del proveedor.",
        );
      }

      mostrarAviso(
        ("message" in respuesta ? respuesta.message : undefined) ??
          (opciones.status === "rejected"
            ? "Proveedor rechazado y reseteado correctamente."
            : "Reset administrativo ejecutado correctamente."),
        "success",
      );
      cerrarModalRevision();
      establecerProveedorSeleccionado(null);
      establecerReviewSeleccionada(null);
      await cargarProveedoresBucket();
      return;
    }

    const respuesta = await ejecutarAccionProveedor(
      proveedorId,
      "review",
      opciones,
    );

    const mensaje = respuesta.message ?? "Revisión guardada correctamente.";

    cerrarModalRevision();
    establecerProveedorSeleccionado(null);
    establecerReviewSeleccionada(null);
    mostrarAviso(mensaje, "success");
    await cargarProveedoresBucket();
  } catch (error) {
    console.error("Error al procesar proveedor:", error);
    const mensaje = extraerMensajeError(error);
    mostrarErrorModal(mensaje);
    mostrarAviso(mensaje, "error");
  } finally {
    establecerAccionEnProceso(null);
  }
}

function manejarAccionesDeProveedores(evento: Event): void {
  const elementoObjetivo = evento.target as HTMLElement;
  const boton = elementoObjetivo.closest<HTMLButtonElement>(
    "[data-provider-action]",
  );

  if (boton?.dataset.providerAction === "review") {
    const proveedorId = boton.dataset.providerId;
    if (proveedorId) {
      void abrirModalRevision(proveedorId);
    }
    return;
  }

  if (boton?.dataset.providerAction === "reset") {
    const proveedorId = boton.dataset.providerId;
    if (proveedorId) {
      void ejecutarAccionSobreProveedor(proveedorId, "reset");
    }
    return;
  }

  if (elementoObjetivo.closest("a, button, input, textarea, select, label")) {
    return;
  }

  const fila = elementoObjetivo.closest<HTMLTableRowElement>(
    "tr[data-provider-id]",
  );
  if (fila && !(elementoObjetivo instanceof HTMLButtonElement)) {
    const proveedorId = fila.dataset.providerId;
    if (proveedorId) {
      void abrirModalRevision(proveedorId);
    }
  }
}

function manejarAccionModal(): void {
  const proveedor = obtenerProveedorSeleccionado();
  if (!proveedor) {
    mostrarErrorModal("Selecciona un proveedor antes de continuar.");
    return;
  }

  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  const revisorInput = obtenerElemento<HTMLInputElement>(
    "#provider-reviewer-name",
  );
  const checklistDocs = obtenerElemento<HTMLInputElement>(
    "#provider-review-check-docs",
  );
  const nombresInput = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-first-names",
  );
  const apellidosInput = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-last-names",
  );
  const cedulaInput = obtenerElemento<HTMLInputElement>(
    "#provider-review-document-id-number",
  );

  const estadoSeleccionado = (estadoSelect?.value ||
    "") as ProviderRecord["status"];
  const reviewer = revisorInput?.value.trim() ?? undefined;
  const documentFirstNames = nombresInput?.value.trim() ?? "";
  const documentLastNames = apellidosInput?.value.trim() ?? "";
  const documentIdNumber = cedulaInput?.value.trim() ?? "";
  const telefono = limpiarTelefono(
    proveedor.contactPhone ?? proveedor.phone ?? "",
  );
  const esEditable = esPerfilProfesionalEditable(proveedor);

  if (!estadoSeleccionado) {
    mostrarErrorModal("Selecciona un resultado antes de continuar.");
    estadoSelect?.focus();
    return;
  }

  if (esEditable && estadoSeleccionado === "approved") {
    void (async () => {
      try {
        establecerAccionEnProceso(proveedor.id);
        await guardarPerfilProfesionalCompletado(proveedor);
      } catch (error) {
        console.error("Error actualizando perfil profesional:", error);
        const mensaje = extraerMensajeError(error);
        mostrarErrorModal(mensaje);
        mostrarAviso(mensaje, "error");
      } finally {
        establecerAccionEnProceso(null);
      }
    })();
    return;
  }

  if (
    estadoSeleccionado === "approved" &&
    checklistDocs &&
    !checklistDocs.checked
  ) {
    mostrarErrorModal("Confirma que revisaste la información del proveedor.");
    checklistDocs.focus();
    return;
  }

  if (
    estadoSeleccionado === "approved" &&
    (!documentFirstNames || !documentLastNames || !documentIdNumber)
  ) {
    mostrarErrorModal(
      "Completa nombres, apellidos y cédula antes de aprobar el proveedor.",
    );
    if (!documentFirstNames) {
      nombresInput?.focus();
    } else if (!documentLastNames) {
      apellidosInput?.focus();
    } else {
      cedulaInput?.focus();
    }
    return;
  }

  void ejecutarAccionSobreProveedor(proveedor.id, "review", {
    status: estadoSeleccionado,
    reviewer,
    phone: telefono ?? undefined,
    documentFirstNames:
      documentFirstNames.length > 0 ? documentFirstNames : undefined,
    documentLastNames:
      documentLastNames.length > 0 ? documentLastNames : undefined,
    documentIdNumber:
      documentIdNumber.length > 0 ? documentIdNumber : undefined,
  });
}

function obtenerReviewServicioPorId(
  reviewId: string,
): ProviderServiceReview | null {
  const proveedor = obtenerProveedorSeleccionado();
  if (!proveedor || !Array.isArray(proveedor.serviceReviews)) {
    return null;
  }

  return proveedor.serviceReviews.find((item) => item.id === reviewId) || null;
}

function establecerAccionReviewEnProceso(reviewId: string | null): void {
  establecerIdReviewEnProceso(reviewId);

  const botones = document.querySelectorAll<HTMLButtonElement>(
    "[data-service-review-action]",
  );
  botones.forEach((boton) => {
    const id = boton.dataset.reviewId || "";
    boton.disabled = Boolean(reviewId) && id === reviewId;
  });

  const botonGuardar = obtenerElemento<HTMLButtonElement>(
    "#provider-service-review-save-btn",
  );
  if (botonGuardar) {
    botonGuardar.disabled = Boolean(reviewId);
  }

  const indicador = obtenerElemento<HTMLSpanElement>(
    "#provider-service-review-processing",
  );
  if (indicador) {
    indicador.style.display = reviewId ? "inline-flex" : "none";
  }
}

async function recargarDetalleProveedorEnModal(): Promise<void> {
  const proveedor = obtenerProveedorSeleccionado();
  if (!proveedor) return;
  await cargarDetalleProveedorSeleccionado(proveedor.id);
}

function abrirModalRevisionServicio(reviewId: string): void {
  const review = obtenerReviewServicioPorId(reviewId);
  if (!review) {
    mostrarAviso("No se encontró la sugerencia seleccionada.", "error");
    return;
  }

  limpiarFormularioRevisionServicio();
  establecerReviewSeleccionada(review);
  actualizarFormularioRevisionServicio(review, obtenerProveedorSeleccionado());

  const modal = obtenerModalRevisionServicio();
  if (modal) {
    modal.show();
  }
}

function construirPayloadRevisionServicioDesdeFormulario(): ProviderServiceReviewActionPayload | null {
  const review = obtenerReviewSeleccionada();
  if (!review) return null;

  const domainCode = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-domain-code",
  )?.value.trim();
  const categoryName = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-category-name",
  )?.value.trim();
  const serviceName = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-service-name",
  )?.value.trim();
  const serviceSummary = obtenerElemento<HTMLTextAreaElement>(
    "#provider-service-review-service-summary",
  )?.value.trim();
  const createDomain = obtenerElemento<HTMLInputElement>(
    "#provider-service-review-create-domain",
  )?.checked;
  const reviewer = obtenerElemento<HTMLInputElement>(
    "#provider-service-reviewer-name",
  )?.value.trim();

  if (!domainCode || !categoryName || !serviceName) {
    return null;
  }

  return {
    domain_code: domainCode,
    category_name: categoryName,
    service_name: serviceName,
    service_summary: serviceSummary || undefined,
    reviewer: reviewer || undefined,
    create_domain_if_missing: Boolean(createDomain),
  };
}

async function manejarGuardadoRevisionServicio(): Promise<void> {
  const review = obtenerReviewSeleccionada();
  if (!review) {
    mostrarAviso("Selecciona una revisión antes de guardar.", "error");
    return;
  }

  const payload = construirPayloadRevisionServicioDesdeFormulario();
  if (!payload) {
    mostrarAviso(
      "Completa dominio, categoría y servicio antes de guardar.",
      "error",
    );
    return;
  }

  try {
    establecerAccionReviewEnProceso(review.id);
    const resultado = await aprobarReviewServicio(review.id, payload);
    mostrarAviso(
      resultado.message ?? "Revisión de servicio aprobada correctamente.",
      "success",
    );
    const modal = obtenerModalRevisionServicio();
    if (modal) {
      modal.hide();
    }
    limpiarFormularioRevisionServicio();
    await recargarDetalleProveedorEnModal();
  } catch (error) {
    console.error("Error guardando revisión de servicio:", error);
    mostrarAviso(extraerMensajeError(error), "error");
  } finally {
    establecerAccionReviewEnProceso(null);
  }
}

async function manejarAccionServicioCatalogo(
  accion: "accept" | "edit",
  reviewId: string,
): Promise<void> {
  const review = obtenerReviewServicioPorId(reviewId);
  if (!review) {
    mostrarAviso("No se encontró la sugerencia seleccionada.", "error");
    return;
  }

  if (accion === "edit") {
    limpiarFormularioRevisionServicio();
    establecerReviewSeleccionada(review);
    actualizarFormularioRevisionServicio(review, obtenerProveedorSeleccionado());
    const modal = obtenerModalRevisionServicio();
    if (modal) {
      modal.show();
    }
    return;
  }

  const proveedor = obtenerProveedorSeleccionado();
  const claveReview = normalizarClaveServicio(
    review.serviceNameNormalized || review.serviceName || review.rawServiceText,
  );
  const servicio = proveedor?.servicesAudit?.find((item) => {
    if (!claveReview) return false;
    const claveServicio = normalizarClaveServicio(
      item.serviceNameNormalized || item.serviceName || item.rawServiceText,
    );
    return claveServicio === claveReview;
  });
  const payload: ProviderServiceReviewActionPayload = {
    domain_code:
      review.suggestedDomainCode ||
      review.assignedDomainCode ||
      servicio?.domainCode ||
      "",
    category_name:
      review.proposedCategoryName ||
      review.assignedCategoryName ||
      servicio?.categoryName ||
      "",
    service_name:
      review.assignedServiceName ||
      review.serviceName ||
      servicio?.serviceName ||
      "",
    service_summary:
      review.proposedServiceSummary ||
      review.assignedServiceSummary ||
      servicio?.serviceSummary ||
      undefined,
    create_domain_if_missing: true,
  };

  if (!payload.domain_code || !payload.category_name || !payload.service_name) {
    mostrarAviso(
      "La sugerencia aún no tiene dominio, categoría o servicio completos.",
      "error",
    );
    return;
  }

  try {
    establecerAccionReviewEnProceso(reviewId);
    const resultado = await aprobarReviewServicio(reviewId, payload);
    mostrarAviso(
      resultado.message ?? "Sugerencia de servicio aprobada correctamente.",
      "success",
    );
    await recargarDetalleProveedorEnModal();
  } catch (error) {
    console.error("Error procesando sugerencia de servicio:", error);
    mostrarAviso(extraerMensajeError(error), "error");
  } finally {
    establecerAccionReviewEnProceso(null);
  }
}

function manejarCopiaTelefono(): void {
  const boton = obtenerElemento<HTMLButtonElement>(
    "#provider-detail-copy-phone",
  );
  const feedback = obtenerElemento<HTMLSpanElement>(
    "#provider-detail-copy-feedback",
  );
  if (!boton) return;
  const telefono = boton.dataset.phone;
  if (!telefono) return;
  void navigator.clipboard
    .writeText(telefono)
    .then(() => {
      if (feedback) {
        feedback.textContent = "Número copiado";
        setTimeout(() => {
          feedback.textContent = "";
        }, 2000);
      }
    })
    .catch(() => {
      if (feedback) {
        feedback.textContent = "No se pudo copiar";
        setTimeout(() => {
          feedback.textContent = "";
        }, 2000);
      }
    });
}

export function enlazarEventos(): void {
  const botonRefrescar = obtenerElemento<HTMLButtonElement>(
    "#providers-refresh-btn",
  );
  if (botonRefrescar) {
    botonRefrescar.addEventListener("click", () => {
      void cargarProveedoresBucket();
    });
  }

  const tabs = document.querySelectorAll<HTMLButtonElement>(
    "[data-provider-bucket]",
  );
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const bucket = tab.dataset.providerBucket as ProviderBucket | undefined;
      if (!bucket || bucket === obtenerBucketActivo()) {
        return;
      }
      establecerBucketActivo(bucket);
      establecerPaginaOperativos(0);
      tabs.forEach((btn) => btn.classList.remove("active"));
      tab.classList.add("active");
      actualizarEncabezadoBucket(obtenerBucketActivo());
      void cargarProveedoresBucket();
    });
  });

  const contenedorKanban = obtenerElemento<HTMLDivElement>(
    "#providers-kanban-wrapper",
  );
  if (contenedorKanban) {
    contenedorKanban.addEventListener("click", (evento) => {
      const objetivo = evento.target as HTMLElement;
      const botonReset = objetivo.closest<HTMLButtonElement>(
        '[data-provider-action="reset"]',
      );
      if (botonReset) {
        manejarAccionesDeProveedores(evento);
        return;
      }
      const boton = objetivo.closest<HTMLButtonElement>(
        "[data-onboarding-jump]",
      );
      if (!boton) return;
      const estadoOnboarding = boton.dataset.onboardingJump;
      if (!estadoOnboarding) return;
      const columna = obtenerElemento<HTMLElement>(
        `#onboarding-column-${estadoOnboarding}`,
      );
      columna?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "start",
      });
    });
  }

  const contenedorTabla = obtenerElemento<HTMLDivElement>(
    "#providers-table-wrapper",
  );
  if (contenedorTabla) {
    contenedorTabla.addEventListener("click", manejarAccionesDeProveedores);
  }

  const botonEnviar = obtenerElemento<HTMLButtonElement>(
    "#provider-review-submit-btn",
  );
  if (botonEnviar) {
    botonEnviar.addEventListener("click", () => manejarAccionModal());
  }

  const botonCopiarTelefono = obtenerElemento<HTMLButtonElement>(
    "#provider-detail-copy-phone",
  );
  if (botonCopiarTelefono) {
    botonCopiarTelefono.addEventListener("click", manejarCopiaTelefono);
  }

  const contenedorServicios = obtenerElemento<HTMLDivElement>(
    "#provider-detail-services",
  );
  if (contenedorServicios) {
    contenedorServicios.addEventListener("click", (evento) => {
      const objetivo = evento.target as HTMLElement;
      const boton = objetivo.closest<HTMLButtonElement>(
        "[data-service-review-action]",
      );
      if (!boton) return;
      const reviewId = boton.dataset.reviewId;
      const accion = boton.dataset.serviceReviewAction as
        | "accept"
        | "edit"
        | undefined;
      if (!reviewId || !accion) return;
      evento.preventDefault();
      void manejarAccionServicioCatalogo(accion, reviewId);
    });
  }

  const botonGuardarRevisionServicio = obtenerElemento<HTMLButtonElement>(
    "#provider-service-review-save-btn",
  );
  if (botonGuardarRevisionServicio) {
    botonGuardarRevisionServicio.addEventListener("click", () => {
      void manejarGuardadoRevisionServicio();
    });
  }

  const botonAgregarServicioProfesional = obtenerElemento<HTMLButtonElement>(
    "#provider-profile-add-service",
  );
  if (botonAgregarServicioProfesional) {
    botonAgregarServicioProfesional.addEventListener("click", () => {
      agregarFilaServicioProfesional("");
    });
  }

  const contenedorServiciosProfesionales = obtenerElemento<HTMLDivElement>(
    "#provider-profile-services-list",
  );
  if (contenedorServiciosProfesionales) {
    contenedorServiciosProfesionales.addEventListener("click", (evento) => {
      manejarAccionesEditorServiciosProfesionales(evento);
    });
  }

  const modalElement = document.getElementById("provider-review-modal");
  if (modalElement) {
    modalElement.addEventListener("hidden.bs.modal", () => {
      establecerProveedorSeleccionado(null);
      limpiarFormularioRevision();
    });
  }

  const modalServicioElement = document.getElementById(
    "provider-service-review-modal",
  );
  if (modalServicioElement) {
    modalServicioElement.addEventListener("hidden.bs.modal", () => {
      limpiarFormularioRevisionServicio();
    });
  }

  const btnPrev = document.querySelector<HTMLButtonElement>("#providers-pagination-prev");
  const btnNext = document.querySelector<HTMLButtonElement>("#providers-pagination-next");

  if (btnPrev) {
    btnPrev.addEventListener("click", () => {
      const pagina = obtenerPaginaOperativos();
      if (pagina > 0) {
        establecerPaginaOperativos(pagina - 1);
        renderizarProveedores(obtenerBucketActivo(), [...obtenerProveedores()], obtenerPaginaOperativos());
      }
    });
  }

  if (btnNext) {
    btnNext.addEventListener("click", () => {
      const pagina = obtenerPaginaOperativos();
      const TAMANO_PAGINA = 50;
      const totalPaginas = Math.ceil(obtenerProveedores().length / TAMANO_PAGINA);
      if (pagina < totalPaginas - 1) {
        establecerPaginaOperativos(pagina + 1);
        renderizarProveedores(obtenerBucketActivo(), [...obtenerProveedores()], obtenerPaginaOperativos());
      }
    });
  }
}
