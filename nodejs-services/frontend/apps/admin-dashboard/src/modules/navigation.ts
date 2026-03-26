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

const SIDEBAR_PINNED_STORAGE_KEY = "tinkubot-admin-sidebar-pinned";

function actualizarTituloMovil(seccion: string, etiqueta: string) {
  const tituloMovil = document.querySelector<HTMLElement>(
    "#mobile-current-section-title",
  );
  if (!tituloMovil) return;

  tituloMovil.textContent = etiqueta || seccion;
}

function sincronizarEstadoDeNavegacion(seccion: string, etiqueta: string) {
  document.querySelectorAll<HTMLElement>("[data-section]").forEach((enlace) => {
    enlace.classList.toggle("active", enlace.dataset.section === seccion);
  });

  actualizarTituloMovil(seccion, etiqueta);
}

function mostrarSeccionActiva(seccion: string) {
  document
    .querySelectorAll<HTMLElement>('[id$="-section"]')
    .forEach((elemento) => {
      elemento.style.display =
        elemento.id === `${seccion}-section` ? "block" : "none";
    });
}

function enfocarSeccionActiva(seccion: string) {
  const selectores: Record<string, string> = {
    dashboard: "#dashboard-section-title",
    providers: "#providers-title",
    monetization: "#monetization-section-title",
    settings: "#settings-section-title",
  };

  const selector = selectores[seccion];
  if (!selector) return;

  const objetivo = document.querySelector<HTMLElement>(selector);
  objetivo?.focus({ preventScroll: true });
}

function cerrarMenuMovilSiAplica(objetivo: HTMLElement) {
  const offcanvas = objetivo.closest(".offcanvas");
  if (!offcanvas) return;

  const bootstrapWindow = window as BootstrapWindow;
  const instancia =
    bootstrapWindow.bootstrap?.Offcanvas?.getInstance(offcanvas);
  instancia?.hide();
}

function manejarClicDeSeccion(evento: Event) {
  evento.preventDefault();
  const objetivo = evento.currentTarget as HTMLElement | null;
  if (!objetivo) return;

  const seccion = objetivo.dataset.section;
  if (!seccion) return;

  const etiqueta =
    objetivo.dataset.sectionLabel ?? objetivo.textContent?.trim() ?? seccion;

  sincronizarEstadoDeNavegacion(seccion, etiqueta);
  mostrarSeccionActiva(seccion);
  enfocarSeccionActiva(seccion);
  cerrarMenuMovilSiAplica(objetivo);
}

function inicializarNavegacionLateral() {
  document.querySelectorAll<HTMLElement>("[data-section]").forEach((enlace) => {
    enlace.addEventListener("click", manejarClicDeSeccion);
  });

  const enlaceActivoInicial = document.querySelector<HTMLElement>(
    "[data-section].active",
  );
  const seccionInicial = enlaceActivoInicial?.dataset.section ?? "dashboard";
  const etiquetaInicial =
    enlaceActivoInicial?.dataset.sectionLabel ??
    enlaceActivoInicial?.textContent?.trim() ??
    "Dashboard";

  sincronizarEstadoDeNavegacion(seccionInicial, etiquetaInicial);
  mostrarSeccionActiva(seccionInicial);
  enfocarSeccionActiva(seccionInicial);
  inicializarSidebarFlotante();
}

function obtenerSidebarPinned(): boolean {
  return localStorage.getItem(SIDEBAR_PINNED_STORAGE_KEY) === "true";
}

function establecerSidebarPinned(pinned: boolean) {
  document.body.classList.toggle("sidebar-pinned", pinned);
  localStorage.setItem(SIDEBAR_PINNED_STORAGE_KEY, String(pinned));
}

function sincronizarBotonSidebar(pinned: boolean) {
  const boton = document.querySelector<HTMLButtonElement>("#sidebar-toggle");
  if (!boton) return;

  boton.setAttribute("aria-pressed", String(pinned));
  boton.setAttribute(
    "aria-label",
    pinned ? "Desfijar menú lateral" : "Fijar menú lateral",
  );
  boton.title = pinned ? "Desfijar menú lateral" : "Fijar menú lateral";

  const icono = boton.querySelector("i");
  if (!icono) return;

  icono.className = pinned ? "fas fa-xmark" : "fas fa-bars";
}

function inicializarSidebarFlotante() {
  const pinned = obtenerSidebarPinned();
  establecerSidebarPinned(pinned);
  sincronizarBotonSidebar(pinned);

  const boton = document.querySelector<HTMLButtonElement>("#sidebar-toggle");
  if (!boton) return;

  boton.addEventListener("click", () => {
    const nuevoEstado = !document.body.classList.contains("sidebar-pinned");
    establecerSidebarPinned(nuevoEstado);
    sincronizarBotonSidebar(nuevoEstado);
  });
}

export const Navigation = {
  iniciar: inicializarNavegacionLateral,
};

export type NavigationModule = typeof Navigation;
