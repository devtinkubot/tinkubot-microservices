type BootstrapOffcanvas = {
  hide: () => void;
};

type BootstrapOffcanvasFactory = {
  getInstance: (elemento: Element) => BootstrapOffcanvas | null;
};

type BootstrapWindow = Window & {
  bootstrap?: {
    Offcanvas?: BootstrapOffcanvasFactory;
  };
};

function actualizarTituloMovil(seccion: string, etiqueta: string) {
  const tituloMovil = document.querySelector<HTMLElement>('#mobile-current-section-title');
  if (!tituloMovil) return;

  tituloMovil.textContent = etiqueta || seccion;
}

function sincronizarEstadoDeNavegacion(seccion: string, etiqueta: string) {
  document.querySelectorAll<HTMLElement>('[data-section]').forEach(enlace => {
    enlace.classList.toggle('active', enlace.dataset.section === seccion);
  });

  actualizarTituloMovil(seccion, etiqueta);
}

function mostrarSeccionActiva(seccion: string) {
  document.querySelectorAll<HTMLElement>('[id$="-section"]').forEach(elemento => {
    elemento.style.display = elemento.id === `${seccion}-section` ? 'block' : 'none';
  });
}

function cerrarMenuMovilSiAplica(objetivo: HTMLElement) {
  const offcanvas = objetivo.closest('.offcanvas');
  if (!offcanvas) return;

  const bootstrapWindow = window as BootstrapWindow;
  const instancia = bootstrapWindow.bootstrap?.Offcanvas?.getInstance(offcanvas);
  instancia?.hide();
}

function manejarClicDeSeccion(evento: Event) {
  evento.preventDefault();
  const objetivo = evento.currentTarget as HTMLElement | null;
  if (!objetivo) return;

  const seccion = objetivo.dataset.section;
  if (!seccion) return;

  const etiqueta = objetivo.dataset.sectionLabel ?? objetivo.textContent?.trim() ?? seccion;

  sincronizarEstadoDeNavegacion(seccion, etiqueta);
  mostrarSeccionActiva(seccion);
  cerrarMenuMovilSiAplica(objetivo);
}

function inicializarNavegacionLateral() {
  document.querySelectorAll<HTMLElement>('[data-section]').forEach(enlace => {
    enlace.addEventListener('click', manejarClicDeSeccion);
  });

  const enlaceActivoInicial = document.querySelector<HTMLElement>('[data-section].active');
  const seccionInicial = enlaceActivoInicial?.dataset.section ?? 'dashboard';
  const etiquetaInicial =
    enlaceActivoInicial?.dataset.sectionLabel ??
    enlaceActivoInicial?.textContent?.trim() ??
    'Dashboard';

  sincronizarEstadoDeNavegacion(seccionInicial, etiquetaInicial);
  mostrarSeccionActiva(seccionInicial);
}

export const Navigation = {
  iniciar: inicializarNavegacionLateral
};

export type NavigationModule = typeof Navigation;
