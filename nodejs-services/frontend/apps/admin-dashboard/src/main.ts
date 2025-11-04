import { Navigation, type NavigationModule } from './modules/navigation';
import { ProvidersManager, type ProvidersManagerModule } from './modules/providersManager';
import { Utils, type UtilsModule } from './modules/utils';
import {
  WhatsAppManager,
  type WhatsAppManagerModule
} from './modules/whatsappManager';

type TinkuBotGlobal = {
  Utils: UtilsModule;
  Navigation: NavigationModule;
  WhatsAppManager: WhatsAppManagerModule;
  ProvidersManager: ProvidersManagerModule;
};

type VentanaDashboard = typeof window & {
  TinkuBot?: TinkuBotGlobal;
  actualizarTodosDatos?: () => Promise<void>;
  regenerarConexionWhatsApp?: (instanceId: string) => Promise<void>;
  recargarProveedoresPendientes?: () => Promise<void>;
};

const ventanaGlobal = window as VentanaDashboard;

ventanaGlobal.TinkuBot = {
  Utils,
  Navigation,
  WhatsAppManager,
  ProvidersManager
};

function enlazarManejadoresGlobales() {
  ventanaGlobal.actualizarTodosDatos = async () => {
    await WhatsAppManager.actualizarTodosDatos();
  };

  ventanaGlobal.regenerarConexionWhatsApp = async (instanceId: string) => {
    await WhatsAppManager.regenerarConexionWhatsApp(instanceId);
  };

  ventanaGlobal.recargarProveedoresPendientes = async () => {
    await ProvidersManager.recargar();
  };
}

document.addEventListener('DOMContentLoaded', () => {
  Navigation.iniciar();
  WhatsAppManager.iniciar();
  WhatsAppManager.cargarEstadoWhatsApp();
  WhatsAppManager.actualizarHoraUltimaActualizacion();
  ProvidersManager.iniciar();
  enlazarManejadoresGlobales();
});
