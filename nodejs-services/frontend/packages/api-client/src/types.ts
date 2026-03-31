export type ProviderStatus = "pending" | "approved" | "rejected";

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

export interface ProviderServiceAudit {
  serviceName?: string | null;
  serviceNameNormalized?: string | null;
  rawServiceText?: string | null;
  serviceSummary?: string | null;
  domainCode?: string | null;
  categoryName?: string | null;
  classificationConfidence?: number | null;
  requiresReview?: boolean | null;
}

export interface ProviderServiceReview {
  id: string;
  providerId?: string | null;
  rawServiceText?: string | null;
  serviceName?: string | null;
  serviceNameNormalized?: string | null;
  suggestedDomainCode?: string | null;
  proposedCategoryName?: string | null;
  proposedServiceSummary?: string | null;
  reviewReason?: string | null;
  reviewStatus?: string | null;
  assignedDomainCode?: string | null;
  assignedCategoryName?: string | null;
  assignedServiceName?: string | null;
  assignedServiceSummary?: string | null;
  reviewedBy?: string | null;
  reviewedAt?: string | null;
  reviewNotes?: string | null;
  publishedProviderServiceId?: string | null;
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
  servicesAudit?: ProviderServiceAudit[];
  serviceReviews?: ProviderServiceReview[];
  experienceRange?: string | null;
  socialMediaUrl?: string | null;
  socialMediaType?: string | null;
  facebookUsername?: string | null;
  instagramUsername?: string | null;
  displayName?: string | null;
  formattedName?: string | null;
  fullName?: string | null;
  firstName?: string | null;
  lastName?: string | null;
  onboardingStep?: string | null;
  onboardingStepUpdatedAt?: string | null;
  documentFirstNames?: string | null;
  documentLastNames?: string | null;
  documentIdNumber?: string | null;
  hasConsent?: boolean | null;
  rating?: number | null;
  documents?: ProviderDocuments;
  certificates?: ProviderCertificate[];
  verificationReviewer?: string | null;
  verificationReviewedAt?: string | null;
  approvedBasicAt?: string | null;
  professionalProfileComplete?: boolean;
}

export interface ProviderActionPayload {
  status?: ProviderStatus;
  reviewer?: string;
  notes?: string;
  phone?: string;
  message?: string;
  documentFirstNames?: string;
  documentLastNames?: string;
  documentIdNumber?: string;
}

export interface ProviderActionResponse {
  providerId: string;
  status: ProviderStatus;
  updatedAt?: string;
  message?: string;
}

export interface ProviderProfessionalProfileUpdatePayload {
  services: string[];
  experienceRange: string;
  socialMediaUrl?: string | null;
  socialMediaType?: string | null;
  facebookUsername?: string | null;
  instagramUsername?: string | null;
}

export interface ProviderProfessionalProfileUpdateResponse {
  ok: boolean;
  providerId?: string;
  services?: string[];
  experienceRange?: string | null;
  socialMediaUrl?: string | null;
  socialMediaType?: string | null;
  facebookUsername?: string | null;
  instagramUsername?: string | null;
  verified?: boolean | null;
  message?: string | null;
  errorReason?: string | null;
}

export interface ProviderServiceReviewActionPayload {
  domain_code: string;
  category_name: string;
  service_name: string;
  service_summary?: string;
  reviewer?: string;
  notes?: string;
  create_domain_if_missing?: boolean;
}

export interface ProviderServiceReviewActionResponse {
  reviewId: string;
  providerId?: string;
  reviewStatus?: string;
  publishedProviderServiceId?: string;
  domainCode?: string;
  createdDomain?: boolean;
  message?: string;
}

export interface ProviderOnboardingResetResponse {
  success: boolean;
  providerId?: string;
  phone?: string | null;
  message?: string;
  sent_whatsapp?: boolean;
  deleted_from_db?: boolean;
  deleted_from_cache?: boolean;
  deleted_related_services?: boolean;
  deleted_storage_assets?: boolean;
  event_type?: string;
  reset_type?: string;
}

export interface ProviderStatusOverviewResponse {
  summary: {
    newPending: number;
    profileComplete: number;
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
