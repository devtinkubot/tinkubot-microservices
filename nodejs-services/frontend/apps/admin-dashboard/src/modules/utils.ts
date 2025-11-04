const API_URL_BASE = '';

export const Utils = {
  obtenerUrlBaseApi: () => API_URL_BASE,
  formatearMarcaDeTiempo: () => new Date().toLocaleString(),
  alternarSpinner: (mostrar: boolean) => {
    const spinner = document.querySelector<HTMLDivElement>('.refresh-btn .loading-spinner');
    if (spinner) {
      spinner.style.display = mostrar ? 'inline-block' : 'none';
    }
  }
};

export type UtilsModule = typeof Utils;
