import {
  apiProveedores,
  type ProviderActionResponse,
  type ProviderRecord
} from '@tinkubot/api-client';

type ErrorConMensaje = Error & { message: string };

function extraerMensajeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (
    error &&
    typeof error === 'object' &&
    'message' in error &&
    typeof (error as ErrorConMensaje).message === 'string'
  ) {
    return (error as ErrorConMensaje).message;
  }
  return 'Ocurrió un error al procesar la solicitud del proveedor.';
}

type TipoAviso = 'success' | 'error' | 'info';

type ProviderBucket = 'new' | 'post_review';

interface EstadoProveedores {
  proveedores: ProviderRecord[];
  estaCargando: boolean;
  idAccionEnProceso: string | null;
  proveedorSeleccionado: ProviderRecord | null;
  bucketActivo: ProviderBucket;
}

interface AccionProveedorOpciones {
  status?: ProviderRecord['status'];
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
  bucketActivo: 'new'
};

const formateadorFecha = new Intl.DateTimeFormat('es-EC', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'America/Guayaquil'
});

const bootstrapGlobal = (window as typeof window & { bootstrap?: { Modal?: any } }).bootstrap;

function obtenerElemento<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

const limpiarTelefono = (valor: string | null | undefined): string | null => {
  if (!valor) return null;
  const limpio = valor.replace(/[^\d+]/g, '');
  return limpio.length > 0 ? limpio : null;
};

function obtenerModalRevision(): ModalInstance | null {
  const modalElement = document.getElementById('provider-review-modal');
  if (!modalElement || !bootstrapGlobal?.Modal) {
    return null;
  }
  return bootstrapGlobal.Modal.getOrCreateInstance(modalElement);
}

function mostrarAviso(mensaje: string, tipo: TipoAviso = 'info') {
  const contenedorAvisos = obtenerElemento<HTMLDivElement>('#providers-feedback');
  if (!contenedorAvisos) return;

  if (!mensaje) {
    contenedorAvisos.style.display = 'none';
    contenedorAvisos.textContent = '';
    contenedorAvisos.className = 'alert';
    return;
  }

  const claseAviso =
    tipo === 'success' ? 'alert-success' : tipo === 'error' ? 'alert-danger' : 'alert-info';
  contenedorAvisos.className = `alert ${claseAviso}`;
  contenedorAvisos.textContent = mensaje;
  contenedorAvisos.style.display = 'block';
}

function establecerTexto(
  selector: string,
  valor: string | null | undefined,
  opciones: { fallback?: string; emptyClass?: string } = {}
) {
  const elemento = obtenerElemento<HTMLElement>(selector);
  if (!elemento) return;
  const { fallback = '—', emptyClass = 'text-muted' } = opciones;

  if (valor && valor.trim().length > 0) {
    elemento.textContent = valor.trim();
    elemento.classList.remove(emptyClass);
  } else {
    elemento.textContent = fallback;
    elemento.classList.add(emptyClass);
  }
}

function formatearFechaLarga(valor?: string | null): string {
  if (!valor) return '—';
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) return valor;
  return formateadorFecha.format(fecha);
}

function obtenerEtiquetaEstadoListado(status?: ProviderRecord['status'] | null): string {
  switch (status) {
    case 'interview_required':
      return 'Entrevista';
    case 'rejected':
      return 'Rechazado';
    case 'approved':
      return 'Aprobado';
    case 'pending':
    default:
      return 'Nuevo';
  }
}

function obtenerClaseEstadoListado(status?: ProviderRecord['status'] | null): string {
  switch (status) {
    case 'interview_required':
      return 'bg-secondary';
    case 'rejected':
      return 'bg-danger';
    case 'approved':
      return 'bg-success';
    case 'pending':
    default:
      return 'bg-warning text-dark';
  }
}

function actualizarEncabezadoBucket() {
  const titulo = obtenerElemento<HTMLElement>('#providers-title');
  const subtitulo = obtenerElemento<HTMLElement>('#providers-subtitle');
  const vacio = obtenerElemento<HTMLElement>('#providers-empty');
  const textoCarga = obtenerElemento<HTMLElement>('#providers-loading')?.querySelector('p');

  if (estado.bucketActivo === 'post_review') {
    if (titulo) titulo.textContent = 'Pendientes post-revisión';
    if (subtitulo) {
      subtitulo.textContent =
        'Gestiona proveedores que ya tuvieron una revisión previa (entrevista o rechazo).';
    }
    if (vacio) vacio.textContent = 'No hay proveedores pendientes post-revisión.';
    if (textoCarga) textoCarga.textContent = 'Obteniendo proveedores post-revisión...';
    return;
  }

  if (titulo) titulo.textContent = 'Proveedores nuevos';
  if (subtitulo) {
    subtitulo.textContent =
      'Revisa y aprueba a los proveedores recién registrados antes de habilitarlos.';
  }
  if (vacio) vacio.textContent = 'No hay proveedores nuevos por revisar.';
  if (textoCarga) textoCarga.textContent = 'Obteniendo proveedores nuevos...';
}

function escaparHtml(texto: string): string {
  return texto.replace(/[&<>"']/g, caracter => {
    const mapa: Record<string, string> = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    };
    return mapa[caracter] ?? caracter;
  });
}

function obtenerServiciosProveedor(proveedor: ProviderRecord): string[] {
  if (Array.isArray(proveedor.servicesList) && proveedor.servicesList.length > 0) {
    return proveedor.servicesList;
  }
  if (typeof proveedor.servicesRaw === 'string' && proveedor.servicesRaw.trim().length > 0) {
    return proveedor.servicesRaw
      .split('|')
      .map(servicio => servicio.trim())
      .filter(servicio => servicio.length > 0);
  }
  return [];
}

function establecerEstadoCarga(estaCargando: boolean) {
  estado.estaCargando = estaCargando;
  const contenedorCarga = obtenerElemento<HTMLDivElement>('#providers-loading');
  if (contenedorCarga) {
    contenedorCarga.style.display = estaCargando ? 'block' : 'none';
  }

  const botonRefrescar = obtenerElemento<HTMLButtonElement>('#providers-refresh-btn');
  if (botonRefrescar) {
    botonRefrescar.disabled = estaCargando;
    const spinner = botonRefrescar.querySelector('.loading-spinner');
    if (spinner instanceof HTMLElement) {
      spinner.style.display = estaCargando ? 'inline-block' : 'none';
    }
  }
}

function mostrarErrorModal(mensaje?: string) {
  const contenedor = obtenerElemento<HTMLDivElement>('#provider-review-error');
  if (!contenedor) return;
  if (mensaje) {
    contenedor.textContent = mensaje;
    contenedor.classList.remove('d-none');
  } else {
    contenedor.textContent = '';
    contenedor.classList.add('d-none');
  }
}

function actualizarDocumentos(proveedor: ProviderRecord) {
  const contenedor = obtenerElemento<HTMLDivElement>('#provider-detail-documents');
  const placeholder = obtenerElemento<HTMLDivElement>('#provider-detail-documents-empty');
  if (!contenedor || !placeholder) return;

  const documentos = proveedor.documents ?? {};
  const items: Array<{ url: string; etiqueta: string }> = [];
  if (documentos.dniFront) {
    items.push({ url: documentos.dniFront, etiqueta: 'Documento identidad - frente' });
  }
  if (documentos.dniBack) {
    items.push({ url: documentos.dniBack, etiqueta: 'Documento identidad - reverso' });
  }
  if (documentos.face) {
    items.push({ url: documentos.face, etiqueta: 'Selfie / Rostro' });
  }

  if (items.length === 0) {
    contenedor.innerHTML = '';
    placeholder.style.display = 'block';
    return;
  }

  const tarjetas = items
    .map(
      item => `
        <div class="col-md-4">
          <div class="provider-document-card">
            <div class="provider-document-thumb">
              <a href="${escaparHtml(item.url)}" target="_blank" rel="noopener noreferrer">
                <img src="${escaparHtml(
                  item.url
                )}" alt="${escaparHtml(item.etiqueta)}" loading="lazy"
                     onerror="this.onerror=null; this.src='data:image/svg+xml;base64,${btoa('<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"100\" height=\"100\" viewBox=\"0 0 100 100\"><rect width=\"100\" height=\"100\" fill=\"#f8f9fa\"/><text x=\"50\" y=\"50\" text-anchor=\"middle\" dy=\".3em\" fill=\"#6c757d\" font-family=\"Arial\" font-size=\"12\">Imagen no disponible</text></svg>')}; this.style.background='#f8f9fa'; this.style.border='1px solid #dee2e6';" />
              </a>
            </div>
            <p class="provider-document-label">${escaparHtml(item.etiqueta)}</p>
          </div>
        </div>
      `
    )
    .join('');

  contenedor.innerHTML = tarjetas;
  placeholder.style.display = 'none';
}

function actualizarServicios(proveedor: ProviderRecord) {
  const contenedor = obtenerElemento<HTMLDivElement>('#provider-detail-services');
  if (!contenedor) return;

  const servicios = obtenerServiciosProveedor(proveedor);
  if (servicios.length === 0) {
    contenedor.innerHTML = '<span class="text-muted">Sin servicios registrados</span>';
    return;
  }

  const chips = servicios
    .map(servicio => `<span class="provider-service-badge">${escaparHtml(servicio)}</span>`)
    .join('');
  contenedor.innerHTML = chips;
}

function actualizarContacto(proveedor: ProviderRecord) {
  const telefono = proveedor.contactPhone ?? proveedor.phone ?? null;
  const email = proveedor.contactEmail ?? proveedor.email ?? null;
  const nombre = proveedor.contact ?? proveedor.name ?? 'Contacto';

  establecerTexto('#provider-detail-phone', telefono, { fallback: 'Sin número' });
  establecerTexto('#provider-detail-contact-name', nombre);
  establecerTexto('#provider-detail-email', email, { fallback: 'Sin correo' });

  const telefonoBtn = obtenerElemento<HTMLButtonElement>('#provider-detail-copy-phone');
  if (telefonoBtn) {
    if (telefono) {
      telefonoBtn.dataset.phone = telefono;
      telefonoBtn.disabled = false;
    } else {
      delete telefonoBtn.dataset.phone;
      telefonoBtn.disabled = true;
    }
  }

  const enlaceWhatsapp = obtenerElemento<HTMLAnchorElement>('#provider-detail-open-whatsapp');
  if (enlaceWhatsapp) {
    if (telefono) {
      const telefonoE164 = telefono.replace(/[^\d+]/g, '');
      enlaceWhatsapp.href = `https://wa.me/${telefonoE164}`;
      enlaceWhatsapp.style.display = 'inline-flex';
    } else {
      enlaceWhatsapp.style.display = 'none';
    }
  }

  const emailLink = obtenerElemento<HTMLAnchorElement>('#provider-detail-email');
  if (emailLink) {
    if (email) {
      emailLink.href = `mailto:${email}`;
      emailLink.classList.remove('text-muted');
      emailLink.style.pointerEvents = 'auto';
      emailLink.tabIndex = 0;
    } else {
      emailLink.href = '#';
      emailLink.classList.add('text-muted');
      emailLink.style.pointerEvents = 'none';
      emailLink.tabIndex = -1;
    }
  }

  const socialWrapper = obtenerElemento<HTMLDivElement>('#provider-detail-social-wrapper');
  const socialLink = obtenerElemento<HTMLAnchorElement>('#provider-detail-social-link');
  if (socialWrapper && socialLink) {
    if (proveedor.socialMediaUrl) {
      socialLink.href = proveedor.socialMediaUrl;
      socialLink.textContent =
        proveedor.socialMediaType && proveedor.socialMediaType.toLowerCase() !== 'otro'
          ? `${proveedor.socialMediaType} · ${proveedor.socialMediaUrl}`
          : proveedor.socialMediaUrl;
      socialWrapper.style.display = 'block';
    } else {
      socialWrapper.style.display = 'none';
    }
  }
}

function actualizarNotas(proveedor: ProviderRecord) {
  const notasPrevias = obtenerElemento<HTMLDivElement>('#provider-detail-existing-notes');
  if (!notasPrevias) return;

  if (proveedor.notes) {
    notasPrevias.innerHTML = `<i class="fas fa-sticky-note me-2 text-primary"></i>${escaparHtml(
      proveedor.notes
    )}`;
  } else {
    notasPrevias.innerHTML =
      '<span class="text-muted">Sin observaciones previas registradas.</span>';
  }

  const notasTextarea = obtenerElemento<HTMLTextAreaElement>('#provider-review-notes');
  if (notasTextarea) {
    notasTextarea.value = proveedor.notes ?? '';
  }
}

function limpiarFormularioRevision() {
  mostrarErrorModal();
  const estadoSelect = obtenerElemento<HTMLSelectElement>('#provider-review-status');
  if (estadoSelect) {
    estadoSelect.value = '';
  }
  const notasTextarea = obtenerElemento<HTMLTextAreaElement>('#provider-review-notes');
  if (notasTextarea) {
    notasTextarea.value = '';
  }
  const mensajeTextarea = obtenerElemento<HTMLTextAreaElement>('#provider-review-message');
  if (mensajeTextarea) {
    mensajeTextarea.value = '';
  }
  const revisorInput = obtenerElemento<HTMLInputElement>('#provider-reviewer-name');
  if (revisorInput) {
    revisorInput.value = '';
  }
  const checklistDocs = obtenerElemento<HTMLInputElement>('#provider-review-check-docs');
  if (checklistDocs) {
    checklistDocs.checked = false;
  }
  const feedback = obtenerElemento<HTMLSpanElement>('#provider-detail-copy-feedback');
  if (feedback) {
    feedback.textContent = '';
  }
  const hiddenId = obtenerElemento<HTMLInputElement>('#provider-review-provider-id');
  if (hiddenId) {
    hiddenId.value = '';
  }
}

function actualizarBadgeEstado(status: ProviderRecord['status']) {
  const badge = obtenerElemento<HTMLSpanElement>('#provider-detail-status-badge');
  if (!badge) return;

  badge.classList.remove(
    'bg-warning',
    'bg-success',
    'bg-danger',
    'bg-secondary',
    'bg-info',
    'text-dark'
  );

  switch (status) {
    case 'approved':
      badge.classList.add('bg-success');
      badge.textContent = 'Aprobado';
      break;
    case 'rejected':
      badge.classList.add('bg-danger');
      badge.textContent = 'Rechazado';
      break;
    case 'interview_required':
      badge.classList.add('bg-secondary');
      badge.textContent = 'Entrevista';
      break;
    default:
      badge.classList.add('bg-warning', 'text-dark');
      badge.textContent = 'Pendiente';
      break;
  }
}

function actualizarDetalleProveedor(proveedor: ProviderRecord) {
  establecerTexto('#provider-detail-name', proveedor.name);
  actualizarBadgeEstado(proveedor.status);
  establecerTexto('#provider-detail-registered', formatearFechaLarga(proveedor.registeredAt));

  const ubicacion =
    proveedor.city && proveedor.province
      ? `${proveedor.city}, ${proveedor.province}`
      : proveedor.city ?? proveedor.province ?? null;
  establecerTexto('#provider-detail-location', ubicacion, {
    fallback: 'Ubicación pendiente'
  });

  establecerTexto(
    '#provider-detail-experience',
    typeof proveedor.experienceYears === 'number'
      ? `${proveedor.experienceYears} año${proveedor.experienceYears === 1 ? '' : 's'}`
      : null,
    { fallback: 'No especifica' }
  );

  establecerTexto(
    '#provider-detail-consent',
    proveedor.hasConsent ? 'Consentimiento registrado' : 'Sin consentimiento',
    { fallback: 'Sin datos' }
  );

  establecerTexto(
    '#provider-detail-rating',
    typeof proveedor.rating === 'number' ? proveedor.rating.toFixed(1) : null,
    { fallback: 'Sin calificación' }
  );

  establecerTexto(
    '#provider-detail-verifier',
    proveedor.verificationReviewer
      ? `${proveedor.verificationReviewer} · ${formatearFechaLarga(proveedor.verificationReviewedAt)}`
      : null,
    { fallback: 'Pendiente de revisión' }
  );

  actualizarServicios(proveedor);
  actualizarContacto(proveedor);
  actualizarDocumentos(proveedor);
  actualizarNotas(proveedor);

  const estadoSelect = obtenerElemento<HTMLSelectElement>('#provider-review-status');
  if (estadoSelect) {
    estadoSelect.value = proveedor.status ?? '';
  }

  const hiddenId = obtenerElemento<HTMLInputElement>('#provider-review-provider-id');
  if (hiddenId) {
    hiddenId.value = proveedor.id;
  }
}

function establecerAccionEnProceso(proveedorId: string | null) {
  estado.idAccionEnProceso = proveedorId;

  const fila = proveedorId
    ? obtenerElemento<HTMLTableRowElement>(`tr[data-provider-id="${proveedorId}"]`)
    : null;

  if (fila) {
    const boton = fila.querySelector<HTMLButtonElement>('[data-provider-action="review"]');
    if (boton) {
      boton.disabled = Boolean(proveedorId);
    }
  }

  const botonEnviar = obtenerElemento<HTMLButtonElement>('#provider-review-submit-btn');
  const indicadorProceso = obtenerElemento<HTMLSpanElement>('#provider-review-processing');

  if (botonEnviar) {
    botonEnviar.disabled = Boolean(proveedorId);
  }

  if (indicadorProceso) {
    indicadorProceso.style.display = proveedorId ? 'inline-flex' : 'none';
  }
}

async function cargarProveedoresBucket() {
  establecerEstadoCarga(true);
  mostrarAviso('');

  try {
    const proveedores =
      estado.bucketActivo === 'post_review'
        ? await apiProveedores.obtenerProveedoresPostRevision()
        : await apiProveedores.obtenerProveedoresNuevos();
    estado.proveedores = proveedores;
    renderizarProveedores();
  } catch (error) {
    console.error('Error al cargar proveedores:', error);
    mostrarAviso(
      error instanceof Error ? error.message : 'No se pudo cargar la lista de proveedores.',
      'error'
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
  const proveedor = estado.proveedores.find(item => item.id === proveedorId);
  if (!proveedor) {
    mostrarAviso('No se encontró la información del proveedor seleccionado.', 'error');
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
  accion: 'review',
  opciones: AccionProveedorOpciones = {}
) {
  establecerAccionEnProceso(proveedorId);
  mostrarErrorModal();

  try {
    let respuesta: ProviderActionResponse;

    respuesta = await apiProveedores.revisarProveedor(proveedorId, opciones);

    const mensaje = respuesta.message ?? 'Revisión guardada correctamente.';

    cerrarModalRevision();
    mostrarAviso(mensaje, 'success');
    await cargarProveedoresBucket();
  } catch (error) {
    console.error('Error al revisar proveedor:', error);
    const mensaje = extraerMensajeError(error);
    mostrarErrorModal(mensaje);
    mostrarAviso(mensaje, 'error');
  } finally {
    establecerAccionEnProceso(null);
  }
}

function manejarAccionesDeProveedores(evento: Event) {
  const elementoObjetivo = evento.target as HTMLElement;
  const boton = elementoObjetivo.closest<HTMLButtonElement>('[data-provider-action]');

  if (boton?.dataset.providerAction === 'review') {
    const proveedorId = boton.dataset.providerId;
    if (proveedorId) {
      abrirModalRevision(proveedorId);
    }
    return;
  }

  const fila = elementoObjetivo.closest<HTMLTableRowElement>('tr[data-provider-id]');
  if (fila && !(elementoObjetivo instanceof HTMLButtonElement)) {
    const proveedorId = fila.dataset.providerId;
    if (proveedorId) {
      abrirModalRevision(proveedorId);
    }
  }
}

function construirMensajeSugerido(
  status: ProviderRecord['status'],
  nombre?: string | null
): string {
  const nombreLimpio = nombre?.trim();
  switch (status) {
    case 'approved':
      return nombreLimpio
        ? `✅ Hola ${nombreLimpio}, tu perfil en TinkuBot fue aprobado. Ya puedes responder solicitudes cuando te escribamos.`
        : '✅ Tu perfil en TinkuBot fue aprobado. Ya puedes responder solicitudes cuando te escribamos.';
    case 'interview_required':
      return nombreLimpio
        ? `Hola ${nombreLimpio}, para continuar con tu registro necesitamos una breve entrevista de validación. Responde a este mensaje para coordinar.`
        : 'Para continuar con tu registro necesitamos una breve entrevista de validación. Responde a este mensaje para coordinar.';
    case 'rejected':
      return nombreLimpio
        ? `Hola ${nombreLimpio}, por ahora no podremos aprobar tu perfil. Si quieres postular más adelante, escríbenos.`
        : 'Por ahora no podremos aprobar tu perfil. Si quieres postular más adelante, escríbenos.';
    default:
      return '';
  }
}

function manejarAccionModal() {
  const proveedor = estado.proveedorSeleccionado;
  if (!proveedor) {
    mostrarErrorModal('Selecciona un proveedor antes de continuar.');
    return;
  }

  const estadoSelect = obtenerElemento<HTMLSelectElement>('#provider-review-status');
  const notasTextarea = obtenerElemento<HTMLTextAreaElement>('#provider-review-notes');
  const mensajeTextarea = obtenerElemento<HTMLTextAreaElement>('#provider-review-message');
  const revisorInput = obtenerElemento<HTMLInputElement>('#provider-reviewer-name');
  const checklistDocs = obtenerElemento<HTMLInputElement>('#provider-review-check-docs');
  const telefonoInput = obtenerElemento<HTMLInputElement>('#provider-phone');

  const estadoSeleccionado = (estadoSelect?.value || '') as ProviderRecord['status'];
  const notas = notasTextarea?.value.trim() ?? '';
  const mensaje = mensajeTextarea?.value.trim() ?? '';
  const reviewer = revisorInput?.value.trim() ?? undefined;
  const telefono = limpiarTelefono(telefonoInput?.value || '');

  if (!estadoSeleccionado) {
    mostrarErrorModal('Selecciona un resultado antes de continuar.');
    estadoSelect?.focus();
    return;
  }

  if (estadoSeleccionado !== 'approved' && mensaje.length === 0) {
    mostrarErrorModal('Ingresa el mensaje que recibirá el proveedor.');
    mensajeTextarea?.focus();
    return;
  }

  if (estadoSeleccionado === 'rejected' && notas.length === 0) {
    mostrarErrorModal('Ingresa un motivo interno de rechazo para continuar.');
    notasTextarea?.focus();
    return;
  }

  if (estadoSeleccionado === 'approved' && checklistDocs && !checklistDocs.checked) {
    mostrarErrorModal('Confirma que revisaste los documentos del proveedor.');
    checklistDocs.focus();
    return;
  }

  void ejecutarAccionSobreProveedor(proveedor.id, 'review', {
    status: estadoSeleccionado,
    notes: notas.length > 0 ? notas : undefined,
    reviewer,
    phone: telefono ?? undefined,
    message: mensaje.length > 0 ? mensaje : undefined
  });
}

function manejarCopiaTelefono() {
  const boton = obtenerElemento<HTMLButtonElement>('#provider-detail-copy-phone');
  const feedback = obtenerElemento<HTMLSpanElement>('#provider-detail-copy-feedback');
  if (!boton) return;
  const telefono = boton.dataset.phone;
  if (!telefono) return;
  void navigator.clipboard
    .writeText(telefono)
    .then(() => {
      if (feedback) {
        feedback.textContent = 'Número copiado';
        setTimeout(() => {
          feedback.textContent = '';
        }, 2000);
      }
    })
    .catch(() => {
      if (feedback) {
        feedback.textContent = 'No se pudo copiar';
        setTimeout(() => {
          feedback.textContent = '';
        }, 2000);
      }
    });
}

function renderizarProveedores() {
  const estadoVacio = obtenerElemento<HTMLDivElement>('#providers-empty');
  const contenedorTabla = obtenerElemento<HTMLDivElement>('#providers-table-wrapper');
  const cuerpoTabla = obtenerElemento<HTMLTableSectionElement>('#providers-table-body');

  if (!contenedorTabla || !cuerpoTabla || !estadoVacio) {
    return;
  }

  if (estado.proveedores.length === 0) {
    contenedorTabla.style.display = 'none';
    cuerpoTabla.innerHTML = '';
    estadoVacio.style.display = 'block';
    return;
  }

  estadoVacio.style.display = 'none';
  contenedorTabla.style.display = 'block';

  const filas = estado.proveedores
    .map(proveedor => {
      const {
        id,
        name,
        businessName,
        contact,
        contactEmail,
        contactPhone,
        registeredAt,
        notes,
        city,
        status
      } = proveedor;

      const infoContacto = [
        contact ?? null,
        contactEmail ? `<span class="text-muted d-block">${escaparHtml(contactEmail)}</span>` : null,
        contactPhone ? `<span class="text-muted d-block">${escaparHtml(contactPhone)}</span>` : null
      ]
        .filter(Boolean)
        .join('');

      const textoNotas = notes ? escaparHtml(notes) : '<span class="text-muted">Sin notas</span>';

      const ubicacion = city ? escaparHtml(city) : '<span class="text-muted">Sin ciudad</span>';

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
    })
    .join('');

  cuerpoTabla.innerHTML = filas;
}

function enlazarEventos() {
  const botonRefrescar = obtenerElemento<HTMLButtonElement>('#providers-refresh-btn');
  if (botonRefrescar) {
    botonRefrescar.addEventListener('click', () => {
      void cargarProveedoresBucket();
    });
  }

  const tabs = document.querySelectorAll<HTMLButtonElement>('[data-provider-bucket]');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const bucket = tab.dataset.providerBucket as ProviderBucket | undefined;
      if (!bucket || bucket === estado.bucketActivo) {
        return;
      }
      estado.bucketActivo = bucket;
      tabs.forEach(btn => btn.classList.remove('active'));
      tab.classList.add('active');
      actualizarEncabezadoBucket();
      void cargarProveedoresBucket();
    });
  });

  const contenedorTabla = obtenerElemento<HTMLDivElement>('#providers-table-wrapper');
  if (contenedorTabla) {
    contenedorTabla.addEventListener('click', manejarAccionesDeProveedores);
  }

  const botonEnviar = obtenerElemento<HTMLButtonElement>('#provider-review-submit-btn');
  if (botonEnviar) {
    botonEnviar.addEventListener('click', () => manejarAccionModal());
  }

  const estadoSelect = obtenerElemento<HTMLSelectElement>('#provider-review-status');
  if (estadoSelect) {
    estadoSelect.addEventListener('change', () => {
      const mensajeTextarea =
        obtenerElemento<HTMLTextAreaElement>('#provider-review-message');
      if (!mensajeTextarea) {
        return;
      }
      const status = estadoSelect.value as ProviderRecord['status'];
      mensajeTextarea.value = construirMensajeSugerido(status, estado.proveedorSeleccionado?.name);
    });
  }

  const botonCopiarTelefono = obtenerElemento<HTMLButtonElement>('#provider-detail-copy-phone');
  if (botonCopiarTelefono) {
    botonCopiarTelefono.addEventListener('click', manejarCopiaTelefono);
  }

  const modalElement = document.getElementById('provider-review-modal');
  if (modalElement) {
    modalElement.addEventListener('hidden.bs.modal', () => {
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
  recargar: cargarProveedoresBucket
};

export type ProvidersManagerModule = typeof ProvidersManager;
