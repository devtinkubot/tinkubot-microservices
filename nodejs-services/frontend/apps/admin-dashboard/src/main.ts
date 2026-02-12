import { Navigation, type NavigationModule } from './modules/navigation';
import {
  MonetizationManager,
  type MonetizationManagerModule
} from './modules/monetizationManager';
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
  MonetizationManager: MonetizationManagerModule;
};

type VentanaDashboard = typeof window & {
  TinkuBot?: TinkuBotGlobal;
  regenerarConexionWhatsApp?: (instanceId: string) => Promise<void>;
  recargarProveedoresPendientes?: () => Promise<void>;
  recargarMonetizacion?: () => Promise<void>;
};

const ventanaGlobal = window as VentanaDashboard;

ventanaGlobal.TinkuBot = {
  Utils,
  Navigation,
  WhatsAppManager,
  ProvidersManager,
  MonetizationManager
};

function enlazarManejadoresGlobales() {
  ventanaGlobal.regenerarConexionWhatsApp = async (instanceId: string) => {
    await WhatsAppManager.regenerarConexionWhatsApp(instanceId);
  };

  ventanaGlobal.recargarProveedoresPendientes = async () => {
    await ProvidersManager.recargar();
  };
  ventanaGlobal.recargarMonetizacion = async () => {
    await MonetizationManager.recargar();
  };
}

document.addEventListener('DOMContentLoaded', () => {
  Navigation.iniciar();
  WhatsAppManager.iniciar();
  WhatsAppManager.actualizarHoraUltimaActualizacion();
  ProvidersManager.iniciar();
  MonetizationManager.iniciar();
  enlazarManejadoresGlobales();
});
