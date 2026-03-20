import { Navigation, type NavigationModule } from "./modules/navigation";
import {
  MonetizationManager,
  type MonetizationManagerModule,
} from "./modules/monetizationManager";
import {
  DashboardManager,
  type DashboardManagerModule,
} from "./modules/dashboardManager";
import {
  ProvidersManager,
  type ProvidersManagerModule,
} from "./modules/providersManager";
import { Utils, type UtilsModule } from "./modules/utils";

type TinkuBotGlobal = {
  Utils: UtilsModule;
  Navigation: NavigationModule;
  DashboardManager: DashboardManagerModule;
  ProvidersManager: ProvidersManagerModule;
  MonetizationManager: MonetizationManagerModule;
};

type VentanaDashboard = typeof window & {
  TinkuBot?: TinkuBotGlobal;
  recargarDashboard?: () => Promise<void>;
  recargarProveedoresPendientes?: () => Promise<void>;
  recargarMonetizacion?: () => Promise<void>;
};

const ventanaGlobal = window as VentanaDashboard;

ventanaGlobal.TinkuBot = {
  Utils,
  Navigation,
  DashboardManager,
  ProvidersManager,
  MonetizationManager,
};

function enlazarManejadoresGlobales() {
  ventanaGlobal.recargarDashboard = async () => {
    await DashboardManager.recargar();
  };
  ventanaGlobal.recargarProveedoresPendientes = async () => {
    await ProvidersManager.recargar();
  };
  ventanaGlobal.recargarMonetizacion = async () => {
    await MonetizationManager.recargar();
  };
}

document.addEventListener("DOMContentLoaded", () => {
  Navigation.iniciar();
  DashboardManager.iniciar();
  ProvidersManager.iniciar();
  MonetizationManager.iniciar();
  enlazarManejadoresGlobales();
});
