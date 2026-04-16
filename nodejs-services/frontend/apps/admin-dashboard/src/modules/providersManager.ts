import { cargarProveedoresBucket, enlazarEventos } from "./providers/providersEventHandlers";
import { actualizarEncabezadoBucket } from "./providers/providersRenderer";
import { obtenerBucketActivo } from "./providers/providersState";

function inicializar(): void {
  enlazarEventos();
  actualizarEncabezadoBucket(obtenerBucketActivo());
  void cargarProveedoresBucket();
}

export const ProvidersManager = {
  iniciar: inicializar,
  recargar: cargarProveedoresBucket,
};

export type ProvidersManagerModule = typeof ProvidersManager;
