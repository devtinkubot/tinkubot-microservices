import { apiWhatsApp, type WhatsAppInstanceStatus } from '@tinkubot/api-client';
import { Utils } from './utils';
import QRCode from 'qrcode';

type TipoMensaje = 'success' | 'error';

type ModalInstance = {
  show: () => void;
  hide: () => void;
};

let instanciaPendiente: string | null = null;
let modalRegenerarQr: ModalInstance | null = null;
let intervaloRefresco: number | null = null;
const REFRESCO_QR_MS = 15000;

function establecerEstadoBotonRecarga(instanciaId: string, estaCargando: boolean) {
  const button = document.querySelector<HTMLButtonElement>(
    `.instance-refresh-btn[data-refresh="${instanciaId}"]`
  );

  if (!button) return;

  button.dataset.loading = estaCargando ? 'true' : 'false';
  button.disabled = estaCargando;
}

function mostrarMensajeDeEstado(
  instanciaId: string,
  mensaje: string,
  tipo: TipoMensaje = 'success'
) {
  const contenedorMensaje = document.getElementById(
    `${instanciaId}-message`
  ) as HTMLDivElement | null;
  if (!contenedorMensaje) return;

  contenedorMensaje.classList.remove('success', 'error');

  if (!mensaje) {
    contenedorMensaje.style.display = 'none';
    contenedorMensaje.textContent = '';
    return;
  }

  contenedorMensaje.textContent = mensaje;
  contenedorMensaje.classList.add(tipo === 'error' ? 'error' : 'success');
  contenedorMensaje.style.display = 'block';
}

function abrirModalRegenerar(instanceId: string) {
  instanciaPendiente = instanceId;
  if (modalRegenerarQr) {
    modalRegenerarQr.show();
  }
}

async function confirmarRegeneracionWhatsApp() {
  if (!instanciaPendiente) return;
  const instanceId = instanciaPendiente;
  instanciaPendiente = null;
  if (modalRegenerarQr) {
    modalRegenerarQr.hide();
  }
  establecerEstadoBotonRecarga(instanceId, true);
  mostrarMensajeDeEstado(instanceId, '');

  const infoDiv = document.getElementById(`${instanceId}-info`);
  if (infoDiv) {
    infoDiv.innerHTML = `
      <p class="text-primary mb-0"><strong>Generando nuevo código QR...</strong></p>
      <p class="text-muted small mb-0">Solicitando nuevo código, espera unos segundos...</p>
    `;
  }

  try {
    const payload = await apiWhatsApp.regenerarInstanciaWhatsApp(instanceId);

    await cargarEstadoWhatsApp();

    const successMessage =
      (typeof payload?.message === 'string' && payload.message) ||
      'Escanea el nuevo código QR generado.';
    mostrarMensajeDeEstado(instanceId, successMessage, 'success');
  } catch (error) {
    console.error('Error al generar QR:', error);
    const message =
      error instanceof Error
        ? error.message
        : 'Ocurrió un problema al generar el nuevo QR.';
    mostrarMensajeDeEstado(instanceId, message, 'error');
  } finally {
    establecerEstadoBotonRecarga(instanceId, false);
  }
}

function actualizarVistaWhatsApp(servicio: string, datos?: WhatsAppInstanceStatus) {
  const indicadorEstado = document.getElementById(`${servicio}-status`);
  const infoDiv = document.getElementById(`${servicio}-info`);
  const qrDiv = document.getElementById(`${servicio}-qr`) as HTMLDivElement | null;
  const messageDiv = document.getElementById(`${servicio}-message`) as HTMLDivElement | null;
  const estado = datos ?? null;

  if (!indicadorEstado || !infoDiv || !qrDiv) {
    return;
  }

  if (estado?.connected) {
    indicadorEstado.className = 'status-indicator connected';
    infoDiv.innerHTML = `
      <p class="text-success mb-0"><strong>Conectado</strong></p>
      <p class="text-muted small mb-0">Listo para enviar mensajes</p>
    `;
    qrDiv.style.display = 'none';
    if (messageDiv) {
      messageDiv.style.display = 'none';
      messageDiv.textContent = '';
      messageDiv.classList.remove('success', 'error');
    }
    return;
  }

  indicadorEstado.className = 'status-indicator disconnected';
  infoDiv.innerHTML = `
    <p class="text-danger mb-0"><strong>Desconectado</strong></p>
    <p class="text-muted small mb-0">Necesita escanear código QR</p>
  `;
  qrDiv.style.display = 'block';

  const qrImage = document.getElementById(`${servicio}-qr-img`) as HTMLImageElement | null;
  if (qrImage) {
    qrImage.src = '';
    qrImage.alt = 'QR no disponible';
  }

  if (estado?.qr && qrImage) {
      // Generar QR code usando la librería qrcode
      QRCode.toDataURL(estado.qr, {
        width: 256,
        margin: 2,
        color: {
          dark: '#000000',
          light: '#FFFFFF'
        }
      })
        .then((url: string) => {
          qrImage.src = url;
          qrImage.alt = 'QR listo para escanear';
        })
        .catch((error: Error) => {
          console.error('Error generando QR:', error);
          qrImage.alt = 'Error generando QR';
        });
  }

  if (messageDiv) {
    messageDiv.style.display = 'none';
    messageDiv.textContent = '';
    messageDiv.classList.remove('success', 'error');
  }
}

async function cargarEstadoWhatsApp(): Promise<void> {
  try {
    const data = await apiWhatsApp.obtenerEstadoWhatsApp();
    actualizarVistaWhatsApp('bot-clientes', data['bot-clientes']);
    actualizarVistaWhatsApp('bot-proveedores', data['bot-proveedores']);
  } catch (error) {
    console.error('Error al cargar estado de WhatsApp:', error);
    mostrarMensajeDeEstado(
      'bot-clientes',
      'No se pudo cargar el estado. Intenta nuevamente.',
      'error'
    );
    mostrarMensajeDeEstado(
      'bot-proveedores',
      'No se pudo cargar el estado. Intenta nuevamente.',
      'error'
    );
  }
}

function actualizarHoraUltimaActualizacion() {
  const timestampElement = document.getElementById('last-update');
  if (timestampElement) {
    timestampElement.textContent = Utils.formatearMarcaDeTiempo();
  }
}

function inicializar() {
  const modalEl = document.getElementById('qr-reset-modal');
  if (modalEl && (window as any).bootstrap) {
    modalRegenerarQr = new (window as any).bootstrap.Modal(modalEl, {
      backdrop: 'static'
    });
  }
  const confirmBtn = document.getElementById('qr-reset-confirm');
  if (confirmBtn) {
    confirmBtn.addEventListener('click', () => {
      confirmarRegeneracionWhatsApp();
    });
  }

  if (intervaloRefresco === null) {
    intervaloRefresco = window.setInterval(() => {
      cargarEstadoWhatsApp();
    }, REFRESCO_QR_MS);
  }
}

export const WhatsAppManager = {
  iniciar: inicializar,
  cargarEstadoWhatsApp,
  regenerarConexionWhatsApp: abrirModalRegenerar,
  actualizarHoraUltimaActualizacion
};

export type WhatsAppManagerModule = typeof WhatsAppManager;
