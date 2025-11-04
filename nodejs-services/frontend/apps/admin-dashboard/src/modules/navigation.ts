function manejarClicDeSeccion(evento: Event) {
  evento.preventDefault();
  const objetivo = evento.currentTarget as HTMLElement | null;
  if (!objetivo) return;

  const seccion = objetivo.dataset.section;
  if (!seccion) return;

  document.querySelectorAll('.sidebar .nav-link').forEach(enlace => {
    enlace.classList.toggle('active', enlace === objetivo);
  });

  document.querySelectorAll<HTMLElement>('[id$="-section"]').forEach(elemento => {
    elemento.style.display = elemento.id === `${seccion}-section` ? 'block' : 'none';
  });
}

function inicializarNavegacionLateral() {
  document.querySelectorAll('.sidebar .nav-link[data-section]').forEach(enlace => {
    enlace.addEventListener('click', manejarClicDeSeccion);
  });
}

export const Navigation = {
  iniciar: inicializarNavegacionLateral
};

export type NavigationModule = typeof Navigation;
