import {
  apiProveedores,
  type ProviderActionResponse,
  type ProviderRecord,
} from "@tinkubot/api-client";
import {
  formatearMarcaTemporalEcuador,
  parsearMarcaTemporalSupabase,
} from "./utils";

type ErrorConMensaje = Error & { message: string };

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

type TipoAviso = "success" | "error" | "info";

type ProviderBucket = "new" | "profile_incomplete";

interface EstadoProveedores {
  proveedores: ProviderRecord[];
  estaCargando: boolean;
  idAccionEnProceso: string | null;
  proveedorSeleccionado: ProviderRecord | null;
  bucketActivo: ProviderBucket;
}

interface AccionProveedorOpciones {
  status?: ProviderRecord["status"];
  notes?: string;
  reviewer?: string;
  phone?: string;
  message?: string;
}

type ModalInstance = {
  show: () => void;
  hide: () => void;
};

const estado: EstadoProveedores = {
  proveedores: [],
  estaCargando: false,
  idAccionEnProceso: null,
  proveedorSeleccionado: null,
  bucketActivo: "new",
};

const formateadorFecha = new Intl.DateTimeFormat("es-EC", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "America/Guayaquil",
});

const bootstrapGlobal = (
  window as typeof window & { bootstrap?: { Modal?: any } }
).bootstrap;

function obtenerElemento<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

const limpiarTelefono = (valor: string | null | undefined): string | null => {
  if (!valor) return null;
  const limpio = valor.replace(/[^\d+]/g, "");
  return limpio.length > 0 ? limpio : null;
};

const limpiarTelefonoWhatsApp = (valor: string | null | undefined): string | null => {
  const telefono = limpiarTelefono(valor);
  if (!telefono) return null;
  const digitos = telefono.replace(/[^\d]/g, "");
  return digitos.length > 0 ? digitos : null;
};

function extraerPrimerNombre(nombreCompleto: string | null | undefined): string {
  const texto = nombreCompleto?.trim();
  if (!texto) return "Proveedor";
  return texto.split(/\s+/).filter(Boolean)[0] || "Proveedor";
}

function construirUrlWhatsApp(telefono: string | null | undefined): string | null {
  const digitos = limpiarTelefonoWhatsApp(telefono);
  if (!digitos) return null;
  return `https://wa.me/${digitos}`;
}

function formatearAntiguedadAprobacion(
  timestamp: string | null | undefined,
): string | null {
  if (!timestamp) return null;
  const fecha = parsearMarcaTemporalSupabase(timestamp);
  if (!fecha) return null;
  const diffMs = Date.now() - fecha.getTime();
  if (!Number.isFinite(diffMs) || diffMs < 0) return null;

  const diffHoras = Math.floor(diffMs / (60 * 60 * 1000));
  if (diffHoras < 1) {
    return "Aprobado hace menos de 1 hora";
  }

  if (diffHoras < 24) {
    return `Aprobado hace ${diffHoras} ${diffHoras === 1 ? "hora" : "horas"}`;
  }

  const diffDias = Math.floor(diffHoras / 24);
  return `Aprobado hace ${diffDias} ${diffDias === 1 ? "día" : "días"}`;
}

function obtenerModalRevision(): ModalInstance | null {
  const modalElement = document.getElementById("provider-review-modal");
  if (!modalElement || !bootstrapGlobal?.Modal) {
    return null;
  }
  return bootstrapGlobal.Modal.getOrCreateInstance(modalElement);
}

function mostrarAviso(mensaje: string, tipo: TipoAviso = "info") {
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
) {
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

function formatearFechaLarga(valor?: string | null): string {
  if (!valor) return "—";
  const formateado = formatearMarcaTemporalEcuador(valor);
  if (formateado !== "—") return formateado;
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) return valor;
  return formateadorFecha.format(fecha);
}

function obtenerEtiquetaEstadoListado(
  status?: ProviderRecord["status"] | null,
): string {
  switch (status) {
    case "approved_basic":
      return "Información personal aprobada";
    case "profile_pending_review":
      return "Revisión legacy";
    case "interview_required":
      return "Entrevista";
    case "rejected":
      return "Rechazado";
    case "approved":
      return "Proveedor operativo";
    case "pending":
    default:
      return "Nuevo";
  }
}

function obtenerClaseEstadoListado(
  status?: ProviderRecord["status"] | null,
): string {
  switch (status) {
    case "approved_basic":
      return "bg-info text-dark";
    case "profile_pending_review":
      return "bg-primary";
    case "interview_required":
      return "bg-secondary";
    case "rejected":
      return "bg-danger";
    case "approved":
      return "bg-success";
    case "pending":
    default:
      return "bg-warning text-dark";
  }
}

function actualizarEncabezadoBucket() {
  const titulo = obtenerElemento<HTMLElement>("#providers-title");
  const subtitulo = obtenerElemento<HTMLElement>("#providers-subtitle");
  const vacio = obtenerElemento<HTMLElement>("#providers-empty");
  const textoCarga =
    obtenerElemento<HTMLElement>("#providers-loading")?.querySelector("p");

  if (estado.bucketActivo === "profile_incomplete") {
    if (titulo) titulo.textContent = "Perfil profesional incompleto";
    if (subtitulo) {
      subtitulo.textContent =
        "Proveedores con información personal aprobada que todavía no completan experiencia y 3 servicios principales.";
    }
    if (vacio)
      vacio.textContent = "No hay perfiles profesionales incompletos.";
    if (textoCarga)
      textoCarga.textContent = "Obteniendo perfiles profesionales incompletos...";
    return;
  }

  if (titulo) titulo.textContent = "Onboarding por revisar";
  if (subtitulo) {
    subtitulo.textContent =
      "Revisa consentimiento, ciudad, identidad y documentos del proveedor antes del alta inicial.";
  }
  if (vacio) vacio.textContent = "No hay onboardings pendientes por revisar.";
  if (textoCarga)
    textoCarga.textContent = "Obteniendo onboardings pendientes...";
}

function escaparHtml(texto: string): string {
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
}

function establecerEstadoCarga(estaCargando: boolean) {
  estado.estaCargando = estaCargando;
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

function mostrarErrorModal(mensaje?: string) {
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

function actualizarDocumentos(proveedor: ProviderRecord) {
  const contenedor = obtenerElemento<HTMLDivElement>(
    "#provider-detail-documents",
  );
  const placeholder = obtenerElemento<HTMLDivElement>(
    "#provider-detail-documents-empty",
  );
  if (!contenedor || !placeholder) return;

  const documentos = proveedor.documents ?? {};
  const items: Array<{ url: string; etiqueta: string }> = [];
  if (documentos.dniFront) {
    items.push({
      url: documentos.dniFront,
      etiqueta: "Documento identidad - frente",
    });
  }
  if (documentos.dniBack) {
    items.push({
      url: documentos.dniBack,
      etiqueta: "Documento identidad - reverso",
    });
  }
  if (documentos.face) {
    items.push({ url: documentos.face, etiqueta: "Foto de perfil / rostro" });
  }

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
                     onerror="this.onerror=null; this.src='data:image/svg+xml;base64,${btoa('<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"100\" height=\"100\" viewBox=\"0 0 100 100\"><rect width=\"100\" height=\"100\" fill=\"#f8f9fa\"/><text x=\"50\" y=\"50\" text-anchor=\"middle\" dy=\".3em\" fill=\"#6c757d\" font-family=\"Arial\" font-size=\"12\">Imagen no disponible</text></svg>')}; this.style.background='#f8f9fa'; this.style.border='1px solid #dee2e6';" />
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

function actualizarCertificados(proveedor: ProviderRecord) {
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

function actualizarContacto(proveedor: ProviderRecord) {
  const telefono =
    proveedor.contactPhone ?? proveedor.realPhone ?? proveedor.phone ?? null;
  const realPhone = proveedor.realPhone ?? null;
  const nombre = proveedor.contact ?? proveedor.name ?? "Contacto";
  const estadoContacto =
    proveedor.contactStatus === "lid_with_real_phone"
      ? "LID con número real confirmado"
      : proveedor.contactStatus === "lid_missing_real_phone"
        ? "LID sin número real"
        : proveedor.contactStatus === "real_phone_available"
          ? "Número real disponible"
          : "Solo teléfono base";

  establecerTexto("#provider-detail-phone", telefono, {
    fallback: "Sin número",
  });
  establecerTexto("#provider-detail-real-phone", realPhone, {
    fallback: "Sin número real",
  });
  establecerTexto("#provider-detail-contact-status", estadoContacto);
  establecerTexto("#provider-detail-contact-name", nombre);

  const telefonoBtn = obtenerElemento<HTMLButtonElement>(
    "#provider-detail-copy-phone",
  );
  if (telefonoBtn) {
    if (telefono) {
      telefonoBtn.dataset.phone = telefono;
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

function actualizarNotas(proveedor: ProviderRecord) {
  const notasPrevias = obtenerElemento<HTMLDivElement>(
    "#provider-detail-existing-notes",
  );
  if (!notasPrevias) return;

  if (proveedor.notes) {
    notasPrevias.innerHTML = `<i class="fas fa-sticky-note me-2 text-primary"></i>${escaparHtml(
      proveedor.notes,
    )}`;
  } else {
    notasPrevias.innerHTML =
      '<span class="text-muted">Sin observaciones previas registradas.</span>';
  }

  const notasTextarea = obtenerElemento<HTMLTextAreaElement>(
    "#provider-review-notes",
  );
  if (notasTextarea) {
    notasTextarea.value = proveedor.notes ?? "";
  }
}

function actualizarPerfilProfesional(proveedor: ProviderRecord) {
  const servicios = obtenerElemento<HTMLDivElement>(
    "#provider-detail-services",
  );
  const experiencia = obtenerElemento<HTMLElement>(
    "#provider-detail-experience",
  );
  const redSocial = obtenerElemento<HTMLElement>(
    "#provider-detail-social-media",
  );
  const tituloPerfil = obtenerElemento<HTMLElement>(
    "#provider-professional-title",
  );
  const lista = Array.isArray(proveedor.servicesList)
    ? proveedor.servicesList.filter(
        (item) => typeof item === "string" && item.trim().length > 0,
      )
    : [];
  const serviciosPrincipales = lista.slice(0, 3);
  const serviciosAdicionales = Math.max(
    lista.length - serviciosPrincipales.length,
    0,
  );
  const experienciaValor =
    typeof proveedor.experienceYears === "number" &&
    Number.isFinite(proveedor.experienceYears)
      ? `${proveedor.experienceYears} año${proveedor.experienceYears === 1 ? "" : "s"}`
      : null;
  const urlRedSocial = proveedor.socialMediaUrl?.trim();
  const tipoRedSocial = proveedor.socialMediaType?.trim();
  const etiquetaRedSocial = urlRedSocial
    ? tipoRedSocial
      ? `${tipoRedSocial}: ${urlRedSocial}`
      : urlRedSocial
    : null;
  if (tituloPerfil) {
    tituloPerfil.textContent = "Servicios del perfil";
  }

  if (servicios) {
    if (serviciosPrincipales.length > 0) {
      servicios.innerHTML = `
        <ul class="mb-0 ps-3">
          ${serviciosPrincipales.map((item) => `<li>${escaparHtml(item)}</li>`).join("")}
        </ul>
        ${
          serviciosAdicionales > 0
            ? `<div class="small text-muted mt-2">+${serviciosAdicionales} servicio(s) adicional(es) fuera de la revisión principal.</div>`
            : ""
        }
      `;
      servicios.classList.remove("text-muted");
    } else {
      servicios.textContent = "Sin servicios registrados";
      servicios.classList.add("text-muted");
    }
  }

  if (experiencia) {
    establecerTexto("#provider-detail-experience", experienciaValor, {
      fallback: "Sin experiencia registrada",
    });
  }

  if (redSocial) {
    if (urlRedSocial && etiquetaRedSocial) {
      redSocial.innerHTML = `<a href="${escaparHtml(urlRedSocial)}" target="_blank" rel="noopener noreferrer">${escaparHtml(
        etiquetaRedSocial,
      )}</a>`;
      redSocial.classList.remove("text-muted");
    } else {
      redSocial.textContent = "Sin red social registrada";
      redSocial.classList.add("text-muted");
    }
  }
}

function actualizarOpcionesResultadoRevision(proveedor: ProviderRecord) {
  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  if (!estadoSelect) return;

  const opciones = [
    { value: "approved_basic", label: "Información personal aprobada" },
    { value: "interview_required", label: "Entrevista requerida" },
    { value: "rejected", label: "Rechazado" },
  ];

  estadoSelect.innerHTML = [
    '<option value="" selected disabled>Selecciona un resultado</option>',
    ...opciones.map(
      (opcion) => `<option value="${opcion.value}">${opcion.label}</option>`,
    ),
  ].join("");
  estadoSelect.value = "";
}

function actualizarCopyRevision(proveedor: ProviderRecord) {
  const tituloBasico = obtenerElemento<HTMLElement>(
    "#provider-basic-section-title",
  );
  const tituloPerfil = obtenerElemento<HTMLElement>(
    "#provider-professional-title",
  );
  const tituloRevision = obtenerElemento<HTMLElement>(
    "#provider-review-section-title",
  );
  const checklist = obtenerElemento<HTMLElement>(
    "#provider-review-check-docs-label",
  );
  const ayudaMensaje = obtenerElemento<HTMLElement>(
    "#provider-review-message-help",
  );
  const ayudaFooter = obtenerElemento<HTMLElement>(
    "#provider-review-footer-help",
  );
  const mensajeTextarea = obtenerElemento<HTMLTextAreaElement>(
    "#provider-review-message",
  );

  if (tituloBasico) {
    tituloBasico.textContent = "Información personal";
  }
  if (tituloPerfil) {
    tituloPerfil.textContent = "Servicios del perfil";
  }
  if (tituloRevision) {
    tituloRevision.textContent = "Revisión administrativa de la información personal";
  }
  if (checklist) {
    checklist.textContent =
      "Confirmo que revisé nombre, ciudad, consentimiento y documentación del proveedor.";
  }
  if (ayudaMensaje) {
    ayudaMensaje.textContent =
      "Se enviará este mensaje al proveedor junto con el resultado del onboarding básico.";
  }
  if (mensajeTextarea) {
    mensajeTextarea.placeholder =
      "Ej. Tu registro básico fue aprobado. Ya puedes ingresar al menú de proveedor.";
  }
  if (ayudaFooter) {
    ayudaFooter.textContent =
      "Se notificará al proveedor vía WhatsApp con el resultado y acceso al menú.";
  }

  actualizarVisibilidadMensajeRevision("");
}

function limpiarFormularioRevision() {
  mostrarErrorModal();
  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  if (estadoSelect) {
    estadoSelect.value = "";
  }
  const notasTextarea = obtenerElemento<HTMLTextAreaElement>(
    "#provider-review-notes",
  );
  if (notasTextarea) {
    notasTextarea.value = "";
  }
  const mensajeTextarea = obtenerElemento<HTMLTextAreaElement>(
    "#provider-review-message",
  );
  if (mensajeTextarea) {
    mensajeTextarea.value = "";
  }
  actualizarVisibilidadMensajeRevision("");
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
}

function actualizarBadgeEstado(status: ProviderRecord["status"]) {
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
    case "approved_basic":
      badge.classList.add("bg-info", "text-dark");
      badge.textContent = "Información personal aprobada";
      break;
    case "profile_pending_review":
      badge.classList.add("bg-primary");
      badge.textContent = "Revisión legacy";
      break;
    case "approved":
      badge.classList.add("bg-success");
      badge.textContent = "Proveedor operativo";
      break;
    case "rejected":
      badge.classList.add("bg-danger");
      badge.textContent = "Rechazado";
      break;
    case "interview_required":
      badge.classList.add("bg-secondary");
      badge.textContent = "Entrevista";
      break;
    default:
      badge.classList.add("bg-warning", "text-dark");
      badge.textContent = "Pendiente";
      break;
  }
}

function actualizarDetalleProveedor(proveedor: ProviderRecord) {
  establecerTexto("#provider-detail-name", proveedor.name);
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
    proveedor.status === "profile_pending_review"
      ? "Revisión legacy"
      : proveedor.status === "approved_basic"
        ? "Información personal aprobada"
        : proveedor.status === "approved"
          ? "Proveedor operativo"
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
  actualizarDocumentos(proveedor);
  actualizarCertificados(proveedor);
  actualizarNotas(proveedor);
  actualizarCopyRevision(proveedor);
  actualizarOpcionesResultadoRevision(proveedor);

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

function establecerAccionEnProceso(proveedorId: string | null) {
  estado.idAccionEnProceso = proveedorId;

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

async function cargarProveedoresBucket() {
  establecerEstadoCarga(true);
  mostrarAviso("");

  try {
    const proveedores =
      estado.bucketActivo === "profile_incomplete"
          ? await apiProveedores.obtenerProveedoresPerfilProfesionalIncompleto()
          : await apiProveedores.obtenerProveedoresNuevos();
    estado.proveedores = proveedores;
    renderizarProveedores();
  } catch (error) {
    console.error("Error al cargar proveedores:", error);
    mostrarAviso(
      error instanceof Error
        ? error.message
        : "No se pudo cargar la lista de proveedores.",
      "error",
    );
    estado.proveedores = [];
    renderizarProveedores();
  } finally {
    establecerEstadoCarga(false);
  }
}

function cerrarModalRevision() {
  const modal = obtenerModalRevision();
  if (modal) {
    modal.hide();
  }
  estado.proveedorSeleccionado = null;
  limpiarFormularioRevision();
}

function abrirModalRevision(proveedorId: string) {
  const proveedor = estado.proveedores.find((item) => item.id === proveedorId);
  if (!proveedor) {
    mostrarAviso(
      "No se encontró la información del proveedor seleccionado.",
      "error",
    );
    return;
  }

  estado.proveedorSeleccionado = proveedor;
  actualizarDetalleProveedor(proveedor);
  mostrarErrorModal();

  const modal = obtenerModalRevision();
  if (modal) {
    modal.show();
  }
}

async function ejecutarAccionSobreProveedor(
  proveedorId: string,
  accion: "review",
  opciones: AccionProveedorOpciones = {},
) {
  establecerAccionEnProceso(proveedorId);
  mostrarErrorModal();

  try {
    let respuesta: ProviderActionResponse;

    respuesta = await apiProveedores.revisarProveedor(proveedorId, opciones);

    const mensaje = respuesta.message ?? "Revisión guardada correctamente.";

    cerrarModalRevision();
    mostrarAviso(mensaje, "success");
    await cargarProveedoresBucket();
  } catch (error) {
    console.error("Error al revisar proveedor:", error);
    const mensaje = extraerMensajeError(error);
    mostrarErrorModal(mensaje);
    mostrarAviso(mensaje, "error");
  } finally {
    establecerAccionEnProceso(null);
  }
}

function manejarAccionesDeProveedores(evento: Event) {
  const elementoObjetivo = evento.target as HTMLElement;
  const boton = elementoObjetivo.closest<HTMLButtonElement>(
    "[data-provider-action]",
  );

  if (boton?.dataset.providerAction === "review") {
    const proveedorId = boton.dataset.providerId;
    if (proveedorId) {
      abrirModalRevision(proveedorId);
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
      abrirModalRevision(proveedorId);
    }
  }
}

function construirMensajeSugerido(
  status: ProviderRecord["status"],
  nombre?: string | null,
): string {
  const nombreLimpio = nombre?.trim();
  switch (status) {
    case "approved_basic":
      return "";
    case "profile_pending_review":
      return nombreLimpio
        ? `✅ Hola *${nombreLimpio}*, estamos revisando tu caso administrativo.`
        : "✅ Estamos revisando tu caso administrativo.";
    case "approved":
      return nombreLimpio
        ? `✅ Hola *${nombreLimpio}*, tu perfil profesional fue aprobado. Ya puedes operar como proveedor en TinkuBot.`
        : "✅ Tu perfil profesional fue aprobado. Ya puedes operar como proveedor en TinkuBot.";
    case "interview_required":
      return nombreLimpio
        ? `Hola ${nombreLimpio}, necesitamos una validación adicional para continuar con tu registro básico. Responde a este mensaje para coordinar el siguiente paso.`
        : "Necesitamos una validación adicional para continuar con tu registro básico. Responde a este mensaje para coordinar el siguiente paso.";
    case "rejected":
      return nombreLimpio
        ? `Hola ${nombreLimpio}, no pudimos aprobar tu registro básico con la información enviada. Revisa tus datos y documentos y vuelve a intentarlo.`
        : "No pudimos aprobar tu registro básico con la información enviada. Revisa tus datos y documentos y vuelve a intentarlo.";
    default:
      return "";
  }
}

function actualizarVisibilidadMensajeRevision(
  status: ProviderRecord["status"] | "",
) {
  const grupoMensaje = obtenerElemento<HTMLElement>(
    "#provider-review-message-group",
  );
  const ayudaFooter = obtenerElemento<HTMLElement>(
    "#provider-review-footer-help",
  );
  const mensajeTextarea = obtenerElemento<HTMLTextAreaElement>(
    "#provider-review-message",
  );
  const usaMensajeEstandar = status === "approved_basic";

  if (grupoMensaje) {
    grupoMensaje.style.display = usaMensajeEstandar ? "none" : "";
  }

  if (mensajeTextarea && usaMensajeEstandar) {
    mensajeTextarea.value = "";
  }

  if (ayudaFooter) {
    ayudaFooter.textContent = usaMensajeEstandar
      ? "Se notificará al proveedor vía WhatsApp con un mensaje estándar y acceso al menú."
      : "Se notificará al proveedor vía WhatsApp con el resultado y el siguiente paso.";
  }
}

function manejarAccionModal() {
  const proveedor = estado.proveedorSeleccionado;
  if (!proveedor) {
    mostrarErrorModal("Selecciona un proveedor antes de continuar.");
    return;
  }

  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  const notasTextarea = obtenerElemento<HTMLTextAreaElement>(
    "#provider-review-notes",
  );
  const mensajeTextarea = obtenerElemento<HTMLTextAreaElement>(
    "#provider-review-message",
  );
  const revisorInput = obtenerElemento<HTMLInputElement>(
    "#provider-reviewer-name",
  );
  const checklistDocs = obtenerElemento<HTMLInputElement>(
    "#provider-review-check-docs",
  );

  const estadoSeleccionado = (estadoSelect?.value ||
    "") as ProviderRecord["status"];
  const notas = notasTextarea?.value.trim() ?? "";
  const mensaje = mensajeTextarea?.value.trim() ?? "";
  const reviewer = revisorInput?.value.trim() ?? undefined;
  const telefono = limpiarTelefono(
    proveedor.contactPhone ?? proveedor.phone ?? "",
  );

  if (!estadoSeleccionado) {
    mostrarErrorModal("Selecciona un resultado antes de continuar.");
    estadoSelect?.focus();
    return;
  }

  if (
    estadoSeleccionado !== "approved_basic" &&
    mensaje.length === 0
  ) {
    mostrarErrorModal("Ingresa el mensaje que recibirá el proveedor.");
    mensajeTextarea?.focus();
    return;
  }

  if (estadoSeleccionado === "rejected" && notas.length === 0) {
    mostrarErrorModal("Ingresa un motivo interno de rechazo para continuar.");
    notasTextarea?.focus();
    return;
  }

  if (
    estadoSeleccionado === "approved_basic" &&
    checklistDocs &&
    !checklistDocs.checked
  ) {
    mostrarErrorModal("Confirma que revisaste los documentos del proveedor.");
    checklistDocs.focus();
    return;
  }

  void ejecutarAccionSobreProveedor(proveedor.id, "review", {
    status: estadoSeleccionado,
    notes: notas.length > 0 ? notas : undefined,
    reviewer,
    phone: telefono ?? undefined,
    message:
      estadoSeleccionado === "approved_basic"
        ? undefined
        : mensaje.length > 0
          ? mensaje
          : undefined,
  });
}

function manejarCopiaTelefono() {
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

function renderizarEncabezadoTabla() {
  const encabezado = obtenerElemento<HTMLTableSectionElement>(
    "#providers-table-head",
  );
  if (!encabezado) return;

  if (estado.bucketActivo === "profile_incomplete") {
    encabezado.innerHTML = `
      <tr>
        <th>Proveedor</th>
        <th>Ciudad</th>
        <th>Aprobado hace</th>
        <th>Contacto</th>
        <th class="text-end">Detalle</th>
      </tr>
    `;
    return;
  }

  encabezado.innerHTML = `
    <tr>
      <th>Proveedor</th>
      <th>Ciudad</th>
      <th>Contacto</th>
      <th>Registrado</th>
      <th>Notas</th>
      <th class="text-end">Revisión</th>
    </tr>
  `;
}

function renderizarFilaProveedorGeneral(proveedor: ProviderRecord): string {
  const {
    id,
    name,
    businessName,
    contact,
    contactPhone,
    registeredAt,
    notes,
    city,
    status,
  } = proveedor;

  const infoContacto = [
    contact ?? null,
    contactPhone
      ? `<span class="text-muted d-block">${escaparHtml(contactPhone)}</span>`
      : null,
  ]
    .filter(Boolean)
    .join("");

  const textoNotas = notes
    ? escaparHtml(notes)
    : '<span class="text-muted">Sin notas</span>';

  const ubicacion = city
    ? escaparHtml(city)
    : '<span class="text-muted">Sin ciudad</span>';

  return `
    <tr data-provider-id="${id}">
      <td>
        <div class="fw-semibold">${escaparHtml(businessName || name)}</div>
        <span class="badge ${obtenerClaseEstadoListado(status)}">
          ${escaparHtml(obtenerEtiquetaEstadoListado(status))}
        </span>
      </td>
      <td>${ubicacion}</td>
      <td>${infoContacto || '<span class="text-muted">Sin contacto</span>'}</td>
      <td>
        <span class="text-muted small">
          ${escaparHtml(formatearFechaLarga(registeredAt))}
        </span>
      </td>
      <td>${textoNotas}</td>
      <td class="text-end">
        <button
          type="button"
          class="btn btn-sm btn-primary"
          data-provider-action="review"
          data-provider-id="${id}"
        >
          <i class="fas fa-eye me-1"></i>
          Revisar
        </button>
      </td>
    </tr>
  `;
}

function renderizarFilaPerfilProfesionalIncompleto(
  proveedor: ProviderRecord,
): string {
  const firstName = extraerPrimerNombre(proveedor.name || proveedor.contact);
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
    <tr data-provider-id="${proveedor.id}">
      <td>
        <div class="fw-semibold">${escaparHtml(firstName)}</div>
        <span class="badge bg-info text-dark">Información personal aprobada</span>
      </td>
      <td>${ciudad}</td>
      <td>${ageMarkup}</td>
      <td>${contactoMarkup}</td>
      <td class="text-end">
        <button
          type="button"
          class="btn btn-sm btn-outline-primary"
          data-provider-action="review"
          data-provider-id="${proveedor.id}"
        >
          <i class="fas fa-eye me-1"></i>
          Ver detalle
        </button>
      </td>
    </tr>
  `;
}

function renderizarProveedores() {
  const estadoVacio = obtenerElemento<HTMLDivElement>("#providers-empty");
  const contenedorTabla = obtenerElemento<HTMLDivElement>(
    "#providers-table-wrapper",
  );
  const cuerpoTabla = obtenerElemento<HTMLTableSectionElement>(
    "#providers-table-body",
  );

  if (!contenedorTabla || !cuerpoTabla || !estadoVacio) {
    return;
  }

  renderizarEncabezadoTabla();

  if (estado.proveedores.length === 0) {
    contenedorTabla.style.display = "none";
    cuerpoTabla.innerHTML = "";
    estadoVacio.style.display = "block";
    return;
  }

  estadoVacio.style.display = "none";
  contenedorTabla.style.display = "block";

  const filas = estado.proveedores
    .map((proveedor) =>
      estado.bucketActivo === "profile_incomplete"
        ? renderizarFilaPerfilProfesionalIncompleto(proveedor)
        : renderizarFilaProveedorGeneral(proveedor),
    )
    .join("");

  cuerpoTabla.innerHTML = filas;
}

function enlazarEventos() {
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
      if (!bucket || bucket === estado.bucketActivo) {
        return;
      }
      estado.bucketActivo = bucket;
      tabs.forEach((btn) => btn.classList.remove("active"));
      tab.classList.add("active");
      actualizarEncabezadoBucket();
      void cargarProveedoresBucket();
    });
  });

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

  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  if (estadoSelect) {
    estadoSelect.addEventListener("change", () => {
      const mensajeTextarea = obtenerElemento<HTMLTextAreaElement>(
        "#provider-review-message",
      );
      const status = estadoSelect.value as ProviderRecord["status"];
      actualizarVisibilidadMensajeRevision(status);
      if (!mensajeTextarea) {
        return;
      }
      mensajeTextarea.value = construirMensajeSugerido(
        status,
        estado.proveedorSeleccionado?.name,
      );
    });
  }

  const botonCopiarTelefono = obtenerElemento<HTMLButtonElement>(
    "#provider-detail-copy-phone",
  );
  if (botonCopiarTelefono) {
    botonCopiarTelefono.addEventListener("click", manejarCopiaTelefono);
  }

  const modalElement = document.getElementById("provider-review-modal");
  if (modalElement) {
    modalElement.addEventListener("hidden.bs.modal", () => {
      estado.proveedorSeleccionado = null;
      limpiarFormularioRevision();
    });
  }
}

function inicializar() {
  enlazarEventos();
  actualizarEncabezadoBucket();
  void cargarProveedoresBucket();
}

export const ProvidersManager = {
  iniciar: inicializar,
  recargar: cargarProveedoresBucket,
};

export type ProvidersManagerModule = typeof ProvidersManager;
