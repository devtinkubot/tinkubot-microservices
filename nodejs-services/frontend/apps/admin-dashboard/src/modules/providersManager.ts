import {
  cargarProveedoresBucket,
  enlazarEventos,
} from "./providers/providersEventHandlers";
import { actualizarEncabezadoBucket } from "./providers/providersRenderer";
import { obtenerBucketActivo } from "./providers/providersState";

function inicializar(): void {
  enlazarEventos();
  actualizarEncabezadoBucket(obtenerBucketActivo());
  void cargarProveedoresBucket();
}

const recargar = cargarProveedoresBucket;

export const ProvidersManager = {
  iniciar: inicializar,
  recargar: recargar,
};

export type ProvidersManagerModule = typeof ProvidersManager;
