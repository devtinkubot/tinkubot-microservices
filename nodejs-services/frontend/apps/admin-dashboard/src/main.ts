import { Navigation, type NavigationModule } from './modules/navigation';
import {
  MonetizationManager,
  type MonetizationManagerModule
} from './modules/monetizationManager';
import { GovernanceManager, type GovernanceManagerModule } from './modules/governanceManager';
import { ProvidersManager, type ProvidersManagerModule } from './modules/providersManager';
import { Utils, type UtilsModule } from './modules/utils';

type TinkuBotGlobal = {
  Utils: UtilsModule;
  Navigation: NavigationModule;
  ProvidersManager: ProvidersManagerModule;
  MonetizationManager: MonetizationManagerModule;
  GovernanceManager: GovernanceManagerModule;
};

type VentanaDashboard = typeof window & {
  TinkuBot?: TinkuBotGlobal;
  recargarProveedoresPendientes?: () => Promise<void>;
  recargarMonetizacion?: () => Promise<void>;
  recargarGobernanza?: () => Promise<void>;
};

const ventanaGlobal = window as VentanaDashboard;

ventanaGlobal.TinkuBot = {
  Utils,
  Navigation,
  ProvidersManager,
  MonetizationManager,
  GovernanceManager
};

function enlazarManejadoresGlobales() {
  ventanaGlobal.recargarProveedoresPendientes = async () => {
    await ProvidersManager.recargar();
  };
  ventanaGlobal.recargarMonetizacion = async () => {
    await MonetizationManager.recargar();
  };
  ventanaGlobal.recargarGobernanza = async () => {
    await GovernanceManager.recargar();
  };
}

document.addEventListener('DOMContentLoaded', () => {
  Navigation.iniciar();
  ProvidersManager.iniciar();
  MonetizationManager.iniciar();
  GovernanceManager.iniciar();
  enlazarManejadoresGlobales();
});
