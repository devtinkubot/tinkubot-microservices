import {
  apiProveedores,
  type ProviderActionResponse,
  type ProviderRecord
} from '@tinkubot/api-client';

type TipoAviso = 'success' | 'error' | 'info';

interface EstadoProveedores {
  proveedores: ProviderRecord[];
  estaCargando: boolean;
  idAccionEnProceso: string | null;
  proveedorSeleccionado: ProviderRecord | null;
}

interface AccionProveedorOpciones {
  notes?: string;
  reviewer?: string;
}

type ModalInstance = {
  show: () => void;
  hide: () => void;
};

const estado: EstadoProveedores = {
  proveedores: [],
  estaCargando: false,
  idAccionEnProceso: null,
  proveedorSeleccionado: null
};

const formateadorFecha = new Intl.DateTimeFormat('es-EC', {
  dateStyle: 'medium',
  timeStyle: 'short'
});

const bootstrapGlobal = (window as typeof window & { bootstrap?: { Modal?: any } }).bootstrap;

function obtenerElemento<T extends HTMLElement>(selector: string): T | null {
  return document.querySelector(selector) as T | null;
}

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
                )}" alt="${escaparHtml(item.etiqueta)}" loading="lazy" />
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
  const notasTextarea = obtenerElemento<HTMLTextAreaElement>('#provider-review-notes');
  if (notasTextarea) {
    notasTextarea.value = '';
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

  badge.classList.remove('bg-warning', 'bg-success', 'bg-danger', 'bg-secondary', 'text-dark');

  switch (status) {
    case 'approved':
      badge.classList.add('bg-success');
      badge.textContent = 'Aprobado';
      break;
    case 'rejected':
      badge.classList.add('bg-danger');
      badge.textContent = 'Rechazado';
      break;
    default:
      badge.classList.add('bg-warning', 'text-dark');
      badge.textContent = 'Pendiente';
      break;
  }
}

function actualizarDetalleProveedor(proveedor: ProviderRecord) {
  establecerTexto('#provider-detail-name', proveedor.name);
  establecerTexto('#provider-detail-profession', proveedor.profession, {
    fallback: 'Sin profesión registrada'
  });
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

  const disponibilidadTexto =
    proveedor.available === true
      ? 'Disponible'
      : proveedor.available === false
        ? 'No disponible'
        : null;

  establecerTexto('#provider-detail-availability', disponibilidadTexto, {
    fallback: 'Sin información'
  });

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

  const botonAprobar = obtenerElemento<HTMLButtonElement>('#provider-review-approve-btn');
  const botonRechazar = obtenerElemento<HTMLButtonElement>('#provider-review-reject-btn');
  const indicadorProceso = obtenerElemento<HTMLSpanElement>('#provider-review-processing');

  [botonAprobar, botonRechazar].forEach(boton => {
    if (boton) {
      boton.disabled = Boolean(proveedorId);
    }
  });

  if (indicadorProceso) {
    indicadorProceso.style.display = proveedorId ? 'inline-flex' : 'none';
  }
}

async function cargarProveedoresPendientes() {
  establecerEstadoCarga(true);
  mostrarAviso('');

  try {
    const proveedores = await apiProveedores.obtenerProveedoresPendientes();
    estado.proveedores = proveedores;
    renderizarProveedores();
  } catch (error) {
    console.error('Error al cargar proveedores pendientes:', error);
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
  accion: 'approve' | 'reject',
  opciones: AccionProveedorOpciones = {}
) {
  establecerAccionEnProceso(proveedorId);
  mostrarErrorModal();

  try {
    let respuesta: ProviderActionResponse;

    if (accion === 'approve') {
      respuesta = await apiProveedores.aprobarProveedor(proveedorId, opciones);
    } else {
      respuesta = await apiProveedores.rechazarProveedor(proveedorId, opciones);
    }

    const mensaje =
      respuesta.message ??
      (accion === 'approve'
        ? 'Proveedor aprobado correctamente.'
        : 'Proveedor rechazado correctamente.');

    cerrarModalRevision();
    mostrarAviso(mensaje, 'success');
    await cargarProveedoresPendientes();
  } catch (error) {
    console.error(`Error al ${accion === 'approve' ? 'aprobar' : 'rechazar'} proveedor:`, error);
    const mensaje =
      error instanceof Error
        ? error.message
        : 'Ocurrió un error al procesar la solicitud del proveedor.';
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

function manejarAccionModal(accion: 'approve' | 'reject') {
  const proveedor = estado.proveedorSeleccionado;
  if (!proveedor) {
    mostrarErrorModal('Selecciona un proveedor antes de continuar.');
    return;
  }

  const notasTextarea = obtenerElemento<HTMLTextAreaElement>('#provider-review-notes');
  const revisorInput = obtenerElemento<HTMLInputElement>('#provider-reviewer-name');
  const checklistDocs = obtenerElemento<HTMLInputElement>('#provider-review-check-docs');

  const notas = notasTextarea?.value.trim() ?? '';
  const reviewer = revisorInput?.value.trim() ?? undefined;

  if (accion === 'reject' && notas.length === 0) {
    mostrarErrorModal('Ingresa un motivo de rechazo para continuar.');
    notasTextarea?.focus();
    return;
  }

  if (accion === 'approve' && checklistDocs && !checklistDocs.checked) {
    mostrarErrorModal('Confirma que revisaste los documentos del proveedor.');
    checklistDocs.focus();
    return;
  }

  void ejecutarAccionSobreProveedor(proveedor.id, accion, {
    notes: notas.length > 0 ? notas : undefined,
    reviewer
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
        profession
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
            ${
              profession
                ? `<span class="text-muted small">${escaparHtml(profession)}</span>`
                : ''
            }
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
      void cargarProveedoresPendientes();
    });
  }

  const contenedorTabla = obtenerElemento<HTMLDivElement>('#providers-table-wrapper');
  if (contenedorTabla) {
    contenedorTabla.addEventListener('click', manejarAccionesDeProveedores);
  }

  const botonAprobar = obtenerElemento<HTMLButtonElement>('#provider-review-approve-btn');
  if (botonAprobar) {
    botonAprobar.addEventListener('click', () => manejarAccionModal('approve'));
  }

  const botonRechazar = obtenerElemento<HTMLButtonElement>('#provider-review-reject-btn');
  if (botonRechazar) {
    botonRechazar.addEventListener('click', () => manejarAccionModal('reject'));
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
  void cargarProveedoresPendientes();
}

export const ProvidersManager = {
  iniciar: inicializar,
  recargar: cargarProveedoresPendientes
};

export type ProvidersManagerModule = typeof ProvidersManager;
