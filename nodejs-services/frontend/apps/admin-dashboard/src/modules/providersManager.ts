import {
  apiProveedores,
  type ProviderOnboardingResetResponse,
  type ProviderActionResponse,
  type ProviderRecord,
  type ProviderProfessionalProfileUpdatePayload,
  type ProviderServiceReview,
  type ProviderServiceReviewActionPayload,
} from "@tinkubot/api-client";
import {
  formatearMarcaTemporalEcuador,
  formatearTelefonoEcuador,
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

type ProviderBucket =
  | "onboarding"
  | "new"
  | "operativos"
  | "profile_incomplete";

type OnboardingColumn = {
  state: string;
  title: string;
};

type OnboardingAgeLevel = "fresh" | "warning" | "critical";

const ONBOARDING_COLUMNS: OnboardingColumn[] = [
  { state: "onboarding_city", title: "Ciudad" },
  { state: "onboarding_dni_front_photo", title: "Cédula frontal" },
  { state: "onboarding_face_photo", title: "Foto de perfil" },
  { state: "onboarding_experience", title: "Experiencia" },
  { state: "onboarding_specialty", title: "Servicios" },
  { state: "onboarding_social_media", title: "Redes sociales" },
];

const EXPERIENCE_RANGE_OPTIONS = [
  "Menos de 1 año",
  "1 a 3 años",
  "3 a 5 años",
  "5 a 10 años",
  "Más de 10 años",
];

interface EstadoProveedores {
  proveedores: ProviderRecord[];
  estaCargando: boolean;
  idAccionEnProceso: string | null;
  idReviewEnProceso: string | null;
  proveedorSeleccionado: ProviderRecord | null;
  reviewSeleccionada: ProviderServiceReview | null;
  bucketActivo: ProviderBucket;
}

interface AccionProveedorOpciones {
  status?: ProviderRecord["status"];
  reviewer?: string;
  phone?: string;
  message?: string;
  documentFirstNames?: string;
  documentLastNames?: string;
  documentIdNumber?: string;
}

type ModalInstance = {
  show: () => void;
  hide: () => void;
};

const estado: EstadoProveedores = {
  proveedores: [],
  estaCargando: false,
  idAccionEnProceso: null,
  idReviewEnProceso: null,
  proveedorSeleccionado: null,
  reviewSeleccionada: null,
  bucketActivo: "onboarding",
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

const limpiarTelefonoWhatsApp = (
  valor: string | null | undefined,
): string | null => {
  const telefono = limpiarTelefono(valor);
  if (!telefono) return null;
  const digitos = telefono.replace(/[^\d]/g, "");
  return digitos.length > 0 ? digitos : null;
};

function extraerPrimerNombre(
  nombreCompleto: string | null | undefined,
): string {
  const texto = nombreCompleto?.trim();
  if (!texto) return "Proveedor";
  return texto.split(/\s+/).filter(Boolean)[0] || "Proveedor";
}

function normalizarClaveServicio(
  valor: string | null | undefined,
): string | null {
  const texto = valor?.trim();
  if (!texto) return null;
  return texto.toLowerCase().replace(/\s+/g, " ");
}

function esIdentificadorWhatsAppCrudo(valor: string): boolean {
  const texto = valor.trim();
  if (!texto) return false;
  if (texto.includes("@s.whatsapp.net") || texto.includes("@lid")) {
    return true;
  }
  return /^\d{8,}$/.test(texto.replace(/[^\d]/g, ""));
}

function resolverTextoVisible(valor: string | null | undefined): string | null {
  const texto = valor?.trim();
  if (!texto) return null;
  return esIdentificadorWhatsAppCrudo(texto)
    ? formatearTelefonoEcuador(texto)
    : texto;
}

function resolverNombreVisibleProveedor(proveedor: ProviderRecord): string {
  const displayName = proveedor.displayName?.trim();
  const formattedName = proveedor.formattedName?.trim();
  const nombreDocumento = [
    proveedor.documentFirstNames?.trim(),
    proveedor.documentLastNames?.trim(),
  ]
    .filter(Boolean)
    .join(" ")
    .trim();

  return nombreDocumento || formattedName || displayName || "Proveedor";
}

function resolverNombreVisibleOperativoProveedor(
  proveedor: ProviderRecord,
): string {
  const nombreDocumento = [
    proveedor.documentFirstNames?.trim(),
    proveedor.documentLastNames?.trim(),
  ]
    .filter(Boolean)
    .join(" ")
    .trim();

  return (
    nombreDocumento ||
    proveedor.displayName?.trim() ||
    proveedor.formattedName?.trim() ||
    "Proveedor"
  );
}

function resolverNombreVisibleSegunBucketActivo(
  proveedor: ProviderRecord,
): string {
  return estado.bucketActivo === "operativos"
    ? resolverNombreVisibleOperativoProveedor(proveedor)
    : resolverNombreVisibleProveedor(proveedor);
}

function resolverTelefonoVisibleOperativoProveedor(
  proveedor: ProviderRecord,
): string | null {
  return (
    resolverTextoVisible(proveedor.contactPhone) ??
    resolverTextoVisible(proveedor.realPhone) ??
    resolverTextoVisible(proveedor.phone)
  );
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

function normalizarPasoOnboarding(proveedor: ProviderRecord): string | null {
  const estado = proveedor.onboardingStep?.trim();
  if (!estado) {
    return null;
  }

  return ONBOARDING_COLUMNS.some((column) => column.state === estado)
    ? estado
    : null;
}

function esPerfilProfesionalEditable(): boolean {
  return estado.bucketActivo === "profile_incomplete";
}

function normalizarListaServiciosEditable(
  servicios: Array<string | null | undefined> | undefined,
): string[] {
  return (servicios || [])
    .map((servicio) => servicio?.trim() || "")
    .filter((servicio) => servicio.length > 0);
}

function construirFilaServicioEditable(valor: string, indice: number): string {
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

function renderizarEditorServiciosProfesionales(servicios: string[]) {
  const contenedor = obtenerElemento<HTMLDivElement>(
    "#provider-profile-services-list",
  );
  if (!contenedor) return;

  const serviciosRender = servicios.length > 0 ? servicios : [""];
  contenedor.innerHTML = serviciosRender
    .map((valor, indice) => construirFilaServicioEditable(valor, indice))
    .join("");
}

function renderizarOpcionesExperienciaProfesional(
  valorSeleccionado: string | null | undefined,
) {
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

function agregarFilaServicioProfesional(valor = "") {
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

function manejarAccionesEditorServiciosProfesionales(evento: Event) {
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

function construirUrlWhatsApp(
  telefono: string | null | undefined,
): string | null {
  const digitos = limpiarTelefonoWhatsApp(telefono);
  if (!digitos) return null;
  return `https://wa.me/${digitos}`;
}

function normalizarTelefonoCopiable(
  telefono: string | null | undefined,
): string | null {
  const digitos = limpiarTelefonoWhatsApp(telefono);
  if (!digitos) return null;
  return `+${digitos}`;
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

function resolverAntiguedadOnboarding(timestamp: string | null | undefined): {
  horas: number | null;
  etiqueta: string | null;
  nivel: OnboardingAgeLevel;
} {
  if (!timestamp) {
    return { horas: null, etiqueta: null, nivel: "fresh" };
  }

  const fecha = parsearMarcaTemporalSupabase(timestamp);
  if (!fecha) {
    return { horas: null, etiqueta: null, nivel: "fresh" };
  }

  const diffMs = Date.now() - fecha.getTime();
  if (!Number.isFinite(diffMs) || diffMs < 0) {
    return { horas: null, etiqueta: null, nivel: "fresh" };
  }

  const horas = Math.floor(diffMs / (60 * 60 * 1000));
  const dias = Math.floor(horas / 24);
  const etiqueta =
    horas < 1
      ? "Hace menos de 1 hora"
      : horas < 24
        ? `Hace ${horas} ${horas === 1 ? "hora" : "horas"}`
        : `Hace ${dias} ${dias === 1 ? "día" : "días"}`;
  const nivel: OnboardingAgeLevel =
    horas >= 72 ? "critical" : horas >= 48 ? "warning" : "fresh";

  return { horas, etiqueta, nivel };
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

  if (estado.bucketActivo === "onboarding") {
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

  if (estado.bucketActivo === "profile_incomplete") {
    if (titulo) titulo.textContent = "Incompletos";
    if (subtitulo) {
      subtitulo.textContent =
        "Proveedores con información personal aprobada que todavía no completan experiencia y al menos 1 servicio.";
    }
    if (vacio) vacio.textContent = "No hay perfiles profesionales incompletos.";
    if (textoCarga)
      textoCarga.textContent =
        "Obteniendo perfiles profesionales incompletos...";
    return;
  }

  if (estado.bucketActivo === "operativos") {
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
  const telefonoPresentable = formatearTelefonoEcuador(telefono);
  const realPhonePresentable = formatearTelefonoEcuador(realPhone);
  const nombre = resolverNombreVisibleSegunBucketActivo(proveedor);
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

function actualizarFotosIdentidad(proveedor: ProviderRecord) {
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

function actualizarCamposIdentidad(proveedor: ProviderRecord) {
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

function obtenerReviewServicioProveedor(
  proveedor: ProviderRecord,
  servicio: {
    serviceName?: string | null;
    serviceNameNormalized?: string | null;
    rawServiceText?: string | null;
  },
): ProviderServiceReview | null {
  const reviews = Array.isArray(proveedor.serviceReviews)
    ? proveedor.serviceReviews.filter(
        (item) => (item.reviewStatus || "").trim().toLowerCase() === "pending",
      )
    : [];
  if (reviews.length === 0) return null;

  const claves = [
    servicio.serviceNameNormalized,
    servicio.serviceName,
    servicio.rawServiceText,
  ]
    .map(normalizarClaveServicio)
    .filter(Boolean) as string[];

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
              data-provider-id="${escaparHtml(estado.proveedorSeleccionado?.id || "")}"
            >
              <i class="fas fa-check me-1"></i>
              Aceptar
            </button>
            <button
              type="button"
              class="btn btn-outline-secondary btn-sm"
              data-service-review-action="edit"
              data-review-id="${escaparHtml(review.id)}"
              data-provider-id="${escaparHtml(estado.proveedorSeleccionado?.id || "")}"
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
            data-provider-id="${escaparHtml(review.providerId || estado.proveedorSeleccionado?.id || "")}"
          >
            <i class="fas fa-check me-1"></i>
            Aceptar
          </button>
          <button
            type="button"
            class="btn btn-outline-secondary btn-sm"
            data-service-review-action="edit"
            data-review-id="${escaparHtml(review.id)}"
            data-provider-id="${escaparHtml(review.providerId || estado.proveedorSeleccionado?.id || "")}"
          >
            <i class="fas fa-pen me-1"></i>
            Editar
          </button>
        </div>
      </td>
    </tr>
  `;
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
  const reviewsUsadas = new Set<string>();
  const experienciaValor = proveedor.experienceRange?.trim() || "Sin definir";
  const urlRedSocial = proveedor.socialMediaUrl?.trim();
  const tipoRedSocial = proveedor.socialMediaType?.trim();
  const etiquetaRedSocial = [tipoRedSocial, urlRedSocial]
    .filter((item) => typeof item === "string" && item.trim().length > 0)
    .join(" / ");

  if (servicios) {
    if (serviciosDetalle.length > 0 || reviewsPendientes.length > 0) {
      const filasServicios = serviciosDetalle
        .map((item, index) => {
          const review = obtenerReviewServicioProveedor(proveedor, item);
          if (review?.id) {
            reviewsUsadas.add(review.id);
          }
          return construirFilaServicioPerfil(item, index, review);
        })
        .join("");
      const filasSinEmparejar = reviewsPendientes
        .filter((review) => !reviewsUsadas.has(review.id))
        .map((review, index) =>
          construirFilaReviewSinEmparejar(
            review,
            serviciosDetalle.length + index,
          ),
        )
        .join("");
      servicios.innerHTML = `
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
      redSocial.innerHTML = urlRedSocial
        ? `<a href="${escaparHtml(urlRedSocial)}" target="_blank" rel="noopener noreferrer">${escaparHtml(
            etiquetaRedSocial,
          )}</a>`
        : escaparHtml(etiquetaRedSocial);
      redSocial.classList.remove("text-muted");
    } else {
      redSocial.textContent = "Sin red social registrada";
      redSocial.classList.add("text-muted");
    }
  }

  actualizarFormularioPerfilProfesional(proveedor);
}

function actualizarFormularioPerfilProfesional(proveedor: ProviderRecord) {
  const esEditable = esPerfilProfesionalEditable();
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
      ? '<i class="fas fa-save me-1"></i> Guardar perfil profesional'
      : '<i class="fas fa-paper-plane me-1"></i> Guardar y notificar';
    botonEnviar.classList.toggle("btn-primary", !esEditable);
    botonEnviar.classList.toggle("btn-success", esEditable);
  }
  if (tituloRevision) {
    tituloRevision.textContent = esEditable
      ? "Completar perfil profesional"
      : "Revisión administrativa del onboarding";
  }
  if (ayudaFooter) {
    ayudaFooter.textContent = esEditable
      ? "Completa experiencia y servicios para mover al proveedor a Operativos."
      : "Se notificará al proveedor vía WhatsApp con el resultado y el siguiente paso.";
  }
  if (checklistLabel && esEditable) {
    checklistLabel.textContent =
      "La validación de identidad ya está completa. Solo falta completar el perfil profesional.";
  }

  if (esEditable) {
    renderizarOpcionesExperienciaProfesional(proveedor.experienceRange);
    renderizarEditorServiciosProfesionales(
      normalizarListaServiciosEditable(proveedor.servicesList),
    );
  }
}

function actualizarOpcionesResultadoRevision(_proveedor: ProviderRecord) {
  const estadoSelect = obtenerElemento<HTMLSelectElement>(
    "#provider-review-status",
  );
  if (!estadoSelect) return;

  const opciones = [
    { value: "approved", label: "Aprobar" },
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

function actualizarCopyRevision(_proveedor: ProviderRecord) {
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
  const esEditable = esPerfilProfesionalEditable();

  if (tituloBasico) {
    tituloBasico.textContent = "Información personal";
  }
  if (tituloRevision) {
    tituloRevision.textContent = esEditable
      ? "Completar perfil profesional"
      : "Validación administrativa";
  }
  if (checklist) {
    checklist.textContent = esEditable
      ? "La validación de identidad ya está completa. Solo falta completar el perfil profesional."
      : "Confirmo que revisé la información, identidad y contacto del proveedor.";
  }
  if (ayudaFooter) {
    ayudaFooter.textContent = esEditable
      ? "Completa experiencia y servicios para mover al proveedor a Operativos."
      : "Se notificará al proveedor vía WhatsApp con el resultado y el siguiente paso.";
  }
}

function actualizarVistaOperativo(_proveedor: ProviderRecord) {
  const esOperativo = estado.bucketActivo === "operativos";
  const esEditable = esPerfilProfesionalEditable();
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
  }
  if (ayudaFooter) {
    ayudaFooter.textContent = esEditable
      ? "Completa experiencia y servicios para mover al proveedor a Operativos."
      : esOperativo
        ? "Detalle operativo de solo lectura."
        : "Se notificará al proveedor vía WhatsApp con el resultado y el siguiente paso.";
  }
  if (tituloRevision) {
    tituloRevision.textContent = esEditable
      ? "Completar perfil profesional"
      : esOperativo
        ? "Detalle operativo"
        : "Revisión administrativa del onboarding";
  }

  [
    checkboxDocs,
    selectorEstado,
    inputRevisor,
    inputNombres,
    inputApellidos,
    inputCedula,
  ].forEach((elemento) => {
    if (elemento) {
      elemento.disabled = esOperativo;
    }
  });
}

function limpiarFormularioRevision() {
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

function actualizarDetalleProveedor(proveedor: ProviderRecord) {
  establecerTexto(
    "#provider-detail-name",
    resolverNombreVisibleSegunBucketActivo(proveedor),
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
      ? "Proveedor aprobado"
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
  actualizarCopyRevision(proveedor);
  actualizarOpcionesResultadoRevision(proveedor);
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
      estado.bucketActivo === "onboarding"
        ? await apiProveedores.obtenerProveedoresOnboarding()
        : estado.bucketActivo === "operativos"
          ? await apiProveedores.obtenerProveedoresOperativos()
          : estado.bucketActivo === "profile_incomplete"
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
  estado.reviewSeleccionada = null;
  limpiarFormularioRevision();
}

async function cargarDetalleProveedorSeleccionado(
  proveedorId: string,
): Promise<void> {
  try {
    const detalle = await apiProveedores.obtenerDetalleProveedor(proveedorId);
    if (estado.proveedorSeleccionado?.id === proveedorId && detalle) {
      estado.proveedorSeleccionado = detalle;
      actualizarDetalleProveedor(detalle);
      if (estado.reviewSeleccionada) {
        const reviewActualizada = Array.isArray(detalle.serviceReviews)
          ? (detalle.serviceReviews.find(
              (item) => item.id === estado.reviewSeleccionada?.id,
            ) ?? null)
          : null;
        if (reviewActualizada) {
          estado.reviewSeleccionada = reviewActualizada;
        }
      }
    }
  } catch (error) {
    console.error("No se pudo recargar el detalle del proveedor:", error);
  }
}

async function guardarPerfilProfesionalCompletado(proveedor: ProviderRecord) {
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
    socialMediaUrl: proveedor.socialMediaUrl?.trim() || undefined,
    socialMediaType: proveedor.socialMediaType?.trim() || undefined,
    facebookUsername: proveedor.facebookUsername?.trim() || undefined,
    instagramUsername: proveedor.instagramUsername?.trim() || undefined,
  };

  const respuesta = await apiProveedores.actualizarPerfilProfesional(
    proveedor.id,
    payload,
  );

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
  await cargarProveedoresBucket();
}

async function abrirModalRevision(proveedorId: string) {
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

  await cargarDetalleProveedorSeleccionado(proveedorId);
}

async function ejecutarAccionSobreProveedor(
  proveedorId: string,
  accion: "review" | "reset",
  opciones: AccionProveedorOpciones = {},
) {
  establecerAccionEnProceso(proveedorId);
  mostrarErrorModal();

  try {
    if (accion === "reset") {
      const confirmado = window.confirm(
        "¿Quieres reiniciar la operación activa de este proveedor? Se eliminará su avance actual y podrá registrarse nuevamente.",
      );
      if (!confirmado) {
        return;
      }

      const respuesta: ProviderOnboardingResetResponse =
        await apiProveedores.resetearProveedorOnboarding(proveedorId);
      if (!respuesta.success) {
        throw new Error(
          respuesta.message ??
            "No se pudo reiniciar el onboarding del proveedor.",
        );
      }

      mostrarAviso(
        respuesta.message ?? "Reset administrativo ejecutado correctamente.",
        "success",
      );
      await cargarProveedoresBucket();
      return;
    }

    const respuesta: ProviderActionResponse =
      await apiProveedores.revisarProveedor(proveedorId, opciones);

    const mensaje = respuesta.message ?? "Revisión guardada correctamente.";

    cerrarModalRevision();
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
      abrirModalRevision(proveedorId);
    }
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

  if (estado.bucketActivo === "profile_incomplete") {
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

  const estadoSeleccionado = (estadoSelect?.value ||
    "") as ProviderRecord["status"];
  const reviewer = revisorInput?.value.trim() ?? undefined;
  const documentFirstNames = nombresInput?.value.trim() ?? "";
  const documentLastNames = apellidosInput?.value.trim() ?? "";
  const documentIdNumber = cedulaInput?.value.trim() ?? "";
  const telefono = limpiarTelefono(
    proveedor.contactPhone ?? proveedor.phone ?? "",
  );

  if (!estadoSeleccionado) {
    mostrarErrorModal("Selecciona un resultado antes de continuar.");
    estadoSelect?.focus();
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
  const proveedor = estado.proveedorSeleccionado;
  if (!proveedor || !Array.isArray(proveedor.serviceReviews)) {
    return null;
  }

  return proveedor.serviceReviews.find((item) => item.id === reviewId) || null;
}

function obtenerServicioAsociadoAReview(review: ProviderServiceReview) {
  const proveedor = estado.proveedorSeleccionado;
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

function obtenerModalRevisionServicio(): ModalInstance | null {
  const modalElement = document.getElementById("provider-service-review-modal");
  if (!modalElement || !bootstrapGlobal?.Modal) return null;
  return bootstrapGlobal.Modal.getOrCreateInstance(modalElement);
}

function limpiarFormularioRevisionServicio() {
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
  estado.reviewSeleccionada = null;
}

function actualizarFormularioRevisionServicio(review: ProviderServiceReview) {
  const provider = estado.proveedorSeleccionado;
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

  if (reviewId) reviewId.value = review.id;
  if (providerId) providerId.value = provider?.id || review.providerId || "";
  if (domainCode) {
    domainCode.value =
      review.suggestedDomainCode ||
      review.assignedDomainCode ||
      obtenerServicioAsociadoAReview(review)?.domainCode ||
      "";
  }
  if (categoryName) {
    categoryName.value =
      review.proposedCategoryName ||
      review.assignedCategoryName ||
      obtenerServicioAsociadoAReview(review)?.categoryName ||
      "";
  }
  if (serviceName) {
    serviceName.value =
      review.assignedServiceName ||
      review.serviceName ||
      obtenerServicioAsociadoAReview(review)?.serviceName ||
      "";
  }
  if (serviceSummary) {
    serviceSummary.value =
      review.proposedServiceSummary ||
      review.assignedServiceSummary ||
      obtenerServicioAsociadoAReview(review)?.serviceSummary ||
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

function establecerAccionReviewEnProceso(reviewId: string | null) {
  estado.idReviewEnProceso = reviewId;

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

async function recargarDetalleProveedorEnModal() {
  const proveedor = estado.proveedorSeleccionado;
  if (!proveedor) return;
  await cargarDetalleProveedorSeleccionado(proveedor.id);
}

function abrirModalRevisionServicio(reviewId: string) {
  const review = obtenerReviewServicioPorId(reviewId);
  if (!review) {
    mostrarAviso("No se encontró la sugerencia seleccionada.", "error");
    return;
  }

  limpiarFormularioRevisionServicio();
  estado.reviewSeleccionada = review;
  actualizarFormularioRevisionServicio(review);

  const modal = obtenerModalRevisionServicio();
  if (modal) {
    modal.show();
  }
}

function construirPayloadRevisionServicioDesdeFormulario(): ProviderServiceReviewActionPayload | null {
  const review = estado.reviewSeleccionada;
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

async function manejarGuardadoRevisionServicio() {
  const review = estado.reviewSeleccionada;
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
    const resultado = await apiProveedores.aprobarReviewServicioCatalogo(
      review.id,
      payload,
    );
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
) {
  const review = obtenerReviewServicioPorId(reviewId);
  if (!review) {
    mostrarAviso("No se encontró la sugerencia seleccionada.", "error");
    return;
  }

  if (accion === "edit") {
    limpiarFormularioRevisionServicio();
    estado.reviewSeleccionada = review;
    actualizarFormularioRevisionServicio(review);
    const modal = obtenerModalRevisionServicio();
    if (modal) {
      modal.show();
    }
    return;
  }

  const servicio = obtenerServicioAsociadoAReview(review);
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
    const resultado = await apiProveedores.aprobarReviewServicioCatalogo(
      reviewId,
      payload,
    );
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
      <th>Nombre</th>
      <th>Contacto</th>
      <th>Ciudad</th>
      <th>Fecha de Registro</th>
      <th class="text-end">Revisión</th>
    </tr>
  `;
}

function renderizarFilaProveedorGeneral(proveedor: ProviderRecord): string {
  const { id, contactPhone, registeredAt, city } = proveedor;
  const nombreVisible = resolverNombreVisibleProveedor(proveedor);
  const telefonoPresentable = formatearTelefonoEcuador(contactPhone);

  const contactoMarkup = telefonoPresentable
    ? escaparHtml(telefonoPresentable)
    : '<span class="text-muted">Sin contacto</span>';

  const ubicacion = city
    ? escaparHtml(city)
    : '<span class="text-muted">Sin ciudad</span>';

  return `
    <tr data-provider-id="${id}">
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
          data-provider-id="${id}"
        >
          <i class="fas fa-eye me-1"></i>
          Revisar
        </button>
      </td>
    </tr>
  `;
}

function renderizarFilaProveedorOperativo(proveedor: ProviderRecord): string {
  const { id, registeredAt, city } = proveedor;
  const nombreVisible = resolverNombreVisibleOperativoProveedor(proveedor);
  const telefonoVisible = resolverTelefonoVisibleOperativoProveedor(proveedor);
  const estadoContacto = obtenerEtiquetaContactoOperativo(proveedor);

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
    <tr data-provider-id="${id}">
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
    <tr data-provider-id="${proveedor.id}">
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
          data-provider-id="${proveedor.id}"
        >
          <i class="fas fa-eye me-1"></i>
          Ver detalle
        </button>
      </td>
    </tr>
  `;
}

function renderizarTarjetaOnboarding(proveedor: ProviderRecord): string {
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

function renderizarTableroOnboarding() {
  const wrapper = obtenerElemento<HTMLDivElement>("#providers-kanban-wrapper");
  const nav = obtenerElemento<HTMLDivElement>("#providers-kanban-nav");
  const board = obtenerElemento<HTMLDivElement>("#providers-kanban-board");
  const estadoVacio = obtenerElemento<HTMLDivElement>("#providers-empty");
  if (!wrapper || !nav || !board || !estadoVacio) {
    return;
  }

  const agrupados = new Map<string, ProviderRecord[]>();
  for (const proveedor of estado.proveedores) {
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
        data-onboarding-jump="${columna.state}"
      >
        ${escaparHtml(columna.title)}
      </button>
    `,
  ).join("");

  board.innerHTML = ONBOARDING_COLUMNS.map((columna) => {
    const proveedores = agrupados.get(columna.state) ?? [];
    const contenido = proveedores.length
      ? proveedores
          .map((proveedor) => renderizarTarjetaOnboarding(proveedor))
          .join("")
      : '<div class="providers-kanban-empty">Sin proveedores en esta fase.</div>';
    return `
      <section
        class="providers-kanban-column"
        id="onboarding-column-${columna.state}"
        data-onboarding-column="${columna.state}"
      >
        <div class="providers-kanban-column-header">
          <div>
            <div class="providers-kanban-column-title">${escaparHtml(columna.title)}</div>
            <div class="providers-kanban-column-key">${escaparHtml(columna.state)}</div>
          </div>
          <span class="providers-kanban-column-count">${proveedores.length}</span>
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

function renderizarProveedores() {
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

  if (estado.bucketActivo === "onboarding") {
    contenedorTabla.style.display = "none";
    cuerpoTabla.innerHTML = "";
    if (contenedorKanban) {
      contenedorKanban.style.display = "block";
    }
    if (estado.proveedores.length === 0) {
      if (contenedorKanban) {
        contenedorKanban.style.display = "none";
      }
      estadoVacio.style.display = "block";
      return;
    }

    estadoVacio.style.display = "none";
    renderizarTableroOnboarding();
    return;
  }

  if (contenedorKanban) {
    contenedorKanban.style.display = "none";
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
        : estado.bucketActivo === "operativos"
          ? renderizarFilaProveedorOperativo(proveedor)
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
      estado.proveedorSeleccionado = null;
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
