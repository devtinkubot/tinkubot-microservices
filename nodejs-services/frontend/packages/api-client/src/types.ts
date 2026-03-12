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
  | 'approved_basic'
  | 'profile_pending_review'
  | 'approved'
  | 'rejected'
  | 'interview_required';

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
  certificates?: ProviderCertificate[];
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

export type TaxonomySuggestionStatus =
  | 'pending'
  | 'enriched'
  | 'approved'
  | 'rejected'
  | 'superseded';

export type TaxonomyProposalType =
  | 'alias'
  | 'new_canonical'
  | 'rule_update'
  | 'review'
  | 'reject';

export interface TaxonomySuggestionEvidence {
  alias_match?: {
    domain_code?: string;
    alias_text?: string;
    alias_normalized?: string;
    similarity?: number;
  } | null;
  provider_service_match?: {
    service_name?: string;
    normalized?: string;
    similarity?: number;
  } | null;
}

export interface TaxonomySuggestionRecord {
  id: string;
  source_channel?: 'client' | 'provider' | 'admin' | 'system' | null;
  source_text?: string | null;
  normalized_text: string;
  context_excerpt?: string | null;
  proposed_domain_code?: string | null;
  proposed_service_candidate?: string | null;
  proposed_canonical_name?: string | null;
  missing_dimensions?: string[] | null;
  proposal_type?: TaxonomyProposalType | null;
  confidence_score?: number | null;
  evidence_json?: TaxonomySuggestionEvidence | null;
  review_status: TaxonomySuggestionStatus;
  cluster_key?: string | null;
  occurrence_count?: number | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TaxonomySuggestionsResponse {
  suggestions: TaxonomySuggestionRecord[];
}

export interface TaxonomySuggestionCluster {
  clusterId: string;
  clusterKey: string;
  representativeSuggestionId: string;
  representative: TaxonomySuggestionRecord;
  reviewStatus: TaxonomySuggestionStatus;
  proposalType?: TaxonomyProposalType | null;
  proposedDomainCode?: string | null;
  proposedCanonicalName?: string | null;
  confidenceScore?: number | null;
  memberCount: number;
  totalOccurrences: number;
  sourceCounts: Record<'client' | 'provider' | 'admin' | 'system', number>;
  variants: string[];
  members: TaxonomySuggestionRecord[];
  firstSeenAt?: string | null;
  lastSeenAt?: string | null;
}

export interface TaxonomySuggestionClustersResponse {
  clusters: TaxonomySuggestionCluster[];
}

export interface TaxonomyOverviewResponse {
  summary: {
    activeVersion?: number | null;
    publishedAt?: string | null;
    domainsPublished: number;
    domainsWithRules: number;
    domainsWithAliases: number;
    domainsWithCanonicals: number;
    totalSuggestions: number;
    totalDrafts: number;
  };
  suggestionStatusCounts: Record<
    'pending' | 'enriched' | 'approved' | 'rejected' | 'superseded',
    number
  >;
  suggestionSourceCounts: Record<'client' | 'provider' | 'admin' | 'system', number>;
  draftStatusCounts: Record<'draft' | 'applied' | 'published' | 'rejected', number>;
  runtimeMetrics7d: {
    totalEvents: number;
    eventCounts: {
      clarificationRequested: number;
      genericServiceBlocked: number;
      genericFallbackUsed: number;
      precisionPromptFallbackUsed: number;
    };
    sourceCounts: Record<'client' | 'provider' | 'admin' | 'system', number>;
    topAmbiguousDomains: Array<{
      domainCode: string;
      clarificationRequested: number;
      genericServiceBlocked: number;
      fallbackUsed: number;
    }>;
  };
}

export interface TaxonomySuggestionReviewPayload {
  reviewStatus: Extract<TaxonomySuggestionStatus, 'pending' | 'rejected'>;
  reviewNotes?: string;
}

export interface TaxonomySuggestionReviewResponse {
  suggestionId?: string;
  clusterId?: string;
  reviewStatus: TaxonomySuggestionStatus;
  updatedAt?: string | null;
}

export interface TaxonomySuggestionApprovePayload {
  approvedBy?: string;
  reviewNotes?: string;
}

export interface TaxonomySuggestionApproveResponse {
  suggestionId?: string;
  clusterId?: string;
  reviewStatus: TaxonomySuggestionStatus;
  changeId: string;
  changeStatus: 'draft' | 'applied' | 'published' | 'rejected';
  updatedAt?: string | null;
}

export interface TaxonomyDraftRecord {
  id: string;
  suggestion_id?: string | null;
  action_type: 'alias' | 'new_canonical' | 'rule_update' | 'review';
  target_domain_code?: string | null;
  proposed_canonical_name?: string | null;
  payload_json?: TaxonomyDraftPayload | null;
  status: 'draft' | 'applied' | 'published' | 'rejected';
  notes?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  applied_at?: string | null;
}

export interface TaxonomyRuleSnapshot {
  id?: string | null;
  required_dimensions?: string[] | null;
  generic_examples?: string[] | null;
  sufficient_examples?: string[] | null;
  client_prompt_template?: string | null;
  provider_prompt_template?: string | null;
  draft_required_dimensions?: string[] | null;
}

export interface TaxonomyDraftPayload {
  source_channel?: string | null;
  source_text?: string | null;
  normalized_text?: string | null;
  context_excerpt?: string | null;
  confidence_score?: number | null;
  occurrence_count?: number | null;
  evidence_json?: TaxonomySuggestionEvidence | null;
  proposed_service_candidate?: string | null;
  missing_dimensions?: string[] | null;
  proposed_aliases?: string[] | null;
  current_rule_snapshot?: TaxonomyRuleSnapshot | null;
  proposed_rule_update?: TaxonomyRuleSnapshot | null;
  diff_summary?: {
    alias_before?: string | null;
    alias_after?: string | null;
    required_dimensions_before?: string[] | null;
    required_dimensions_after?: string[] | null;
  } | null;
  apply_strategy?: string | null;
  current_canonical_name?: string | null;
  applied_alias_id?: string | null;
  applied_alias_text?: string | null;
  applied_alias_normalized?: string | null;
  applied_canonical_service_id?: string | null;
  applied_canonical_name?: string | null;
  applied_rule_id?: string | null;
  applied_at?: string | null;
  published_at?: string | null;
  published_version?: number | null;
}

export interface TaxonomyDraftsResponse {
  items: TaxonomyDraftRecord[];
}

export interface TaxonomyDraftApplyResponse {
  changeId: string;
  status: 'draft' | 'applied' | 'published' | 'rejected';
  aliasId?: string | null;
  updatedAt?: string | null;
}

export interface TaxonomyPublishResponse {
  version: number;
  publishedCount: number;
  publishedAt: string;
}
