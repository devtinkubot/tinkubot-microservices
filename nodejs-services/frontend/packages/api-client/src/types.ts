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

export type ProviderStatus = 'pending' | 'approved' | 'rejected';

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
  profession?: string | null;
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
  reviewer?: string;
  notes?: string;
}

export interface ProviderActionResponse {
  providerId: string;
  status: ProviderStatus;
  updatedAt?: string;
  message?: string;
}
