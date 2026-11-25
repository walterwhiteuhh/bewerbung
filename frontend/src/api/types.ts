// Spiegelt die Pydantic-Schemas aus src/bewerbung/domain/schemas.py.

export const STATUSES = [
  "saved",
  "applied",
  "in_review",
  "interview",
  "offer",
  "accepted",
  "rejected",
  "withdrawn",
] as const;
export type ApplicationStatus = (typeof STATUSES)[number];

export const SOURCES = [
  "linkedin",
  "stepstone",
  "xing",
  "indeed",
  "arbeitsagentur",
  "glassdoor",
  "personio",
  "greenhouse",
  "lever",
  "softgarden",
  "join",
  "workday",
  "adzuna",
  "jooble",
  "arbeitnow",
  "remotive",
  "manual",
  "other",
] as const;
export type JobSource = (typeof SOURCES)[number];

export const REMOTE_TYPES = ["onsite", "hybrid", "remote", "unknown"] as const;
export type RemoteType = (typeof REMOTE_TYPES)[number];

export type SortField = "created_at" | "updated_at" | "status_changed_at" | "priority" | "title";

export interface Company {
  id: number;
  name: string;
  logo_url: string | null;
  website: string | null;
  industry: string | null;
  location: string | null;
  logo_source: "portal" | "website" | "manual" | null;
  social_links: SocialLinks;
  posting_count?: number | null;
}

export type SocialNetwork = "linkedin" | "xing" | "kununu" | "instagram" | "facebook" | "youtube" | "x" | "tiktok" | "github";
export type SocialLinks = Partial<Record<SocialNetwork, string>>;

export interface CompanyUpdate {
  name?: string;
  website?: string | null;
  industry?: string | null;
  location?: string | null;
  logo_url?: string | null;
  social_links?: string[] | null;
}

export interface ApplicationSummary {
  id: number;
  current_status: ApplicationStatus;
  status_changed_at: string;
  applied_at: string | null;
  priority: number;
  follow_up_at: string | null;
}

export interface StatusEvent {
  id: number;
  from_status: ApplicationStatus | null;
  to_status: ApplicationStatus;
  note: string | null;
  occurred_at: string;
  recorded_at: string;
}

export interface Note {
  id: number;
  body: string;
  created_at: string;
  updated_at: string;
}

export interface Application extends ApplicationSummary {
  posting_id: number;
  contact_name: string | null;
  contact_email: string | null;
  created_at: string;
  updated_at: string;
  events: StatusEvent[];
  notes: Note[];
}

export interface PostingListItem {
  id: number;
  title: string;
  company: Company | null;
  location: string | null;
  remote_type: RemoteType;
  source: JobSource;
  url: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  created_at: string;
  updated_at: string;
  application: ApplicationSummary | null;
  tags: string[];
}

export interface PostingDetail extends Omit<PostingListItem, "application"> {
  employment_type: string | null;
  description: string | null;
  external_id: string | null;
  url_normalized: string | null;
  posted_at: string | null;
  archived_at: string | null;
  application: Application | null;
}

export interface PostingPage {
  items: PostingListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PostingInput {
  title: string;
  company_name?: string | null;
  url?: string | null;
  location?: string | null;
  remote_type?: RemoteType;
  employment_type?: string | null;
  salary_min?: number | null;
  salary_max?: number | null;
  description?: string | null;
  salary_currency?: string;
  posted_at?: string | null;
  raw_payload?: Record<string, unknown> | null;
  initial_status?: ApplicationStatus;
  priority?: number;
  tags?: string[];
}

export interface TagCount {
  name: string;
  count: number;
}

export interface SourceDetection {
  source: JobSource;
  external_id: string | null;
  url_normalized: string;
  duplicate_of: number | null;
}

export interface ImportPreview {
  detection: SourceDetection;
  method: "json-ld" | "opengraph" | "none";
  title: string | null;
  company_name: string | null;
  company_logo_url: string | null;
  location: string | null;
  remote_type: RemoteType;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  description: string | null;
  posted_at: string | null;
  raw_payload: Record<string, unknown>;
  suggested_tags: string[];
  warnings: string[];
}

export interface CountBucket {
  key: string;
  count: number;
}

export interface Stats {
  total: number;
  active: number;
  by_status: CountBucket[];
  by_source: CountBucket[];
  response_rate: number | null;
}

export interface PostingFilter {
  q: string;
  status: ApplicationStatus[];
  source: JobSource[];
  remote: RemoteType[];
  tag: string[];
  location: string;
  minSalary: number | null;
  followUpDue: boolean;
  includeArchived: boolean;
  sort: SortField;
  order: "asc" | "desc";
}

// --- Live-Suche -----------------------------------------------------------------

export interface ProviderInfo {
  source: JobSource;
  label: string;
  available: boolean;
  reason: string | null;
}

export interface Listing {
  id: number;
  posting_id: number | null;
  source: JobSource;
  external_id: string | null;
  url: string | null;
  title: string;
  company_name: string | null;
  company_logo_url: string | null;
  location: string | null;
  remote_type: RemoteType;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  description: string | null;
  posted_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
}

export interface SearchHit {
  rank: number;
  is_new: boolean;
  listing: Listing;
  features: JobFeatures | null;
}

export interface CompanyActivity {
  company_id: number;
  listings: number;
  active_listings: number;
  portals: JobSource[];
  website: string | null;
  social_links: SocialLinks;
  saved_postings: number;
  applications: number;
  rejections: number;
  last_status: ApplicationStatus | null;
}

export interface SimilarJob {
  kind: "posting" | "listing";
  id: number;
  title: string;
  company_name: string | null;
  score: number;
  shared: string[];
}

export interface JobFeatures {
  city: string | null;
  postal_code: string | null;
  region: string | null;
  lat: number | null;
  lon: number | null;
  position_estimated: boolean;
  distance_km: number | null;
  distance_estimated: boolean;
  within_max_distance: boolean | null;
  age_days: number | null;
  days_online: number | null;
  times_seen: number;
  portals: JobSource[];
  is_repost: boolean;
  match_score: number | null;
  matched_skills: string[];
  missing_skills: string[];
  company: CompanyActivity | null;
  similar_saved: SimilarJob | null;
}

export interface ListingBrief {
  id: number;
  posting_id: number | null;
  source: JobSource;
  title: string;
  company_name: string | null;
  city: string | null;
  url: string | null;
  last_seen_at: string;
}

export interface PostingInsights {
  features: JobFeatures;
  other_portals: ListingBrief[];
  same_company_postings: SimilarJob[];
  same_company_listings: ListingBrief[];
  similar: SimilarJob[];
}

export const WORK_TIMES = ["vollzeit", "teilzeit", "minijob", "schicht"] as const;
export type WorkTime = (typeof WORK_TIMES)[number];
export const OFFER_TYPES = ["arbeit", "ausbildung", "praktikum", "selbststaendig"] as const;
export type OfferType = (typeof OFFER_TYPES)[number];

export interface SearchParams {
  query: string;
  location: string | null;
  radius_km: number | null;
  remote_only: boolean;
  work_times: WorkTime[];
  offer_type: OfferType;
  sources: JobSource[];
  profile_id?: number | null;
}

export interface SearchRunSummary {
  id: number;
  profile_id: number | null;
  query: string;
  location: string | null;
  radius_km: number | null;
  remote_only: boolean;
  work_times: WorkTime[];
  offer_type: OfferType;
  sources: string[];
  started_at: string;
  finished_at: string | null;
  total_hits: number;
  new_hits: number;
  errors: { source: string; message: string }[];
}

export interface SearchRun extends SearchRunSummary {
  hits: SearchHit[];
}

export interface SearchProfile {
  id: number;
  name: string;
  query: string;
  location: string | null;
  radius_km: number | null;
  remote_only: boolean;
  work_times: WorkTime[];
  offer_type: OfferType;
  sources: JobSource[];
  created_at: string;
}

// --- Anschreiben -----------------------------------------------------------

export interface Profile {
  full_name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  headline: string | null;
  summary: string | null;
  skills: string[];
  cv_text: string | null;
  signature: string | null;
  home_location: string | null;
  home_located?: boolean;
  home_lat?: number | null;
  home_lon?: number | null;
  max_distance_km: number | null;
  updated_at?: string | null;
}

export type GeneratorName = "claude" | "openai" | "gemini" | "template";
export type LetterTone = "formell" | "modern" | "locker";
export type LetterLength = "kurz" | "normal" | "ausfuehrlich";

export interface GeneratorInfo {
  name: GeneratorName;
  label: string;
  available: boolean;
  reason: string | null;
  model: string | null;
}

export interface LetterRequest {
  generator: "auto" | GeneratorName;
  tone: LetterTone;
  length: LetterLength;
  extra_notes: string | null;
}

export interface CoverLetter {
  id: number;
  posting_id: number;
  version: number;
  status: "draft" | "final";
  body: string;
  edited: boolean;
  generator: GeneratorName;
  model: string | null;
  tone: LetterTone;
  input_snapshot: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface LetterContext {
  portal: string | null;
  tags: string[];
  suggested_tags: string[];
  description_excerpt: string | null;
  matching_skills: string[];
  profile_complete: boolean;
  missing_profile_fields: string[];
}

// --- Unterlagen ------------------------------------------------------------

export const DOCUMENT_KINDS = ["lebenslauf", "zeugnis", "zertifikat", "anschreiben", "sonstiges"] as const;
export type DocumentKind = (typeof DOCUMENT_KINDS)[number];

export interface DocumentInfo {
  id: number;
  kind: DocumentKind;
  title: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  page_count: number | null;
  has_text: boolean;
  text_preview: string | null;
  is_primary: boolean;
  created_at: string;
  archived_at: string | null;
}
