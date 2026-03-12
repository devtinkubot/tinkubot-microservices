import { Navigation, type NavigationModule } from './modules/navigation';
import {
  MonetizationManager,
  type MonetizationManagerModule
} from './modules/monetizationManager';
import { ProvidersManager, type ProvidersManagerModule } from './modules/providersManager';
import {
  TaxonomySuggestionsManager,
  type TaxonomySuggestionsManagerModule
} from './modules/taxonomySuggestionsManager';
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
  TaxonomySuggestionsManager: TaxonomySuggestionsManagerModule;
};

type VentanaDashboard = typeof window & {
  TinkuBot?: TinkuBotGlobal;
  regenerarConexionWhatsApp?: (instanceId: string) => Promise<void>;
  recargarProveedoresPendientes?: () => Promise<void>;
  recargarMonetizacion?: () => Promise<void>;
  recargarTaxonomia?: () => Promise<void>;
};

const ventanaGlobal = window as VentanaDashboard;

ventanaGlobal.TinkuBot = {
  Utils,
  Navigation,
  WhatsAppManager,
  ProvidersManager,
  MonetizationManager,
  TaxonomySuggestionsManager
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
  ventanaGlobal.recargarTaxonomia = async () => {
    await TaxonomySuggestionsManager.recargar();
  };
}

document.addEventListener('DOMContentLoaded', () => {
  Navigation.iniciar();
  WhatsAppManager.iniciar();
  WhatsAppManager.actualizarHoraUltimaActualizacion();
  ProvidersManager.iniciar();
  MonetizationManager.iniciar();
  TaxonomySuggestionsManager.iniciar();
  enlazarManejadoresGlobales();
});
