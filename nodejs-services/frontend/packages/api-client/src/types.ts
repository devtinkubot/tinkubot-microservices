export type WhatsAppInstanceKey = 'bot-clientes' | 'bot-proveedores' | string;

export interface WhatsAppInstanceStatus {
  connected: boolean;
  qr?: string | null;
  phone?: string | null;
  battery?: number | null;
}

export interface WhatsAppStatusResponse {
  [key: WhatsAppInstanceKey]: WhatsAppInstanceStatus | undefined;
}

export type ProviderStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'interview_required';

export interface ProviderDocuments {
  dniFront?: string | null;
  dniBack?: string | null;
  face?: string | null;
}

export interface ProviderRecord {
  id: string;
  name: string;
  businessName?: string;
  contact?: string;
  contactEmail?: string;
  contactPhone?: string;
  phone?: string | null;
  email?: string | null;
  registeredAt: string;
  status: ProviderStatus;
  notes?: string | null;
  city?: string | null;
  province?: string | null;
  servicesRaw?: string | null;
  servicesList?: string[];
  experienceYears?: number | null;
  socialMediaUrl?: string | null;
  socialMediaType?: string | null;
  hasConsent?: boolean | null;
  rating?: number | null;
  documents?: ProviderDocuments;
  verificationReviewer?: string | null;
  verificationReviewedAt?: string | null;
}

export interface ProviderActionPayload {
  status?: ProviderStatus;
  reviewer?: string;
  notes?: string;
  phone?: string;
  message?: string;
}

export interface ProviderActionResponse {
  providerId: string;
  status: ProviderStatus;
  updatedAt?: string;
  message?: string;
}

export type MonetizationBillingStatus = 'active' | 'paused_paywall' | 'suspended';

export interface MonetizationOverview {
  activeProviders: number;
  pausedProviders: number;
  leadsShared7d: number;
  leadsShared30d: number;
  hiredYes30d: number;
  hiredNo30d: number;
  hiredRate30d: number | null;
}

export interface MonetizationProviderRecord {
  providerId: string;
  name: string;
  phone?: string | null;
  city?: string | null;
  billingStatus: MonetizationBillingStatus;
  freeLeadsRemaining: number;
  paidLeadsRemaining: number;
  leadsShared30d: number;
  hiredYes30d: number;
  hiredNo30d: number;
  lastLeadAt?: string | null;
}

export interface MonetizationProvidersResponse {
  items: MonetizationProviderRecord[];
  pagination: {
    limit: number;
    offset: number;
    count: number;
  };
}
