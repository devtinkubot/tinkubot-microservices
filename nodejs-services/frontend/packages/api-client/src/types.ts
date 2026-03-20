export type ProviderStatus =
  | "pending"
  | "approved_basic"
  | "profile_pending_review"
  | "approved"
  | "rejected"
  | "interview_required";

export interface ProviderDocuments {
  dniFront?: string | null;
  dniBack?: string | null;
  face?: string | null;
}

export interface ProviderCertificate {
  id?: string;
  fileUrl: string;
  displayOrder?: number | null;
  status?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface ProviderRecord {
  id: string;
  name: string;
  businessName?: string;
  contact?: string;
  contactPhone?: string;
  phone?: string | null;
  realPhone?: string | null;
  contactStatus?:
    | "lid_with_real_phone"
    | "lid_missing_real_phone"
    | "real_phone_available"
    | "basic_phone_only";
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
  certificates?: ProviderCertificate[];
  verificationReviewer?: string | null;
  verificationReviewedAt?: string | null;
  approvedBasicAt?: string | null;
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

export interface ProviderStatusOverviewResponse {
  summary: {
    newPending: number;
    personalApproved: number;
    professionalToComplete: number;
    professionalUnderReview: number;
    profileComplete: number;
    total: number;
  };
}

export type MonetizationBillingStatus =
  | "active"
  | "paused_paywall"
  | "suspended";

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
