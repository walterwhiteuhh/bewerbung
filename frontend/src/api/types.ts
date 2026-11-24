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

export const SOURCES = ["linkedin", "stepstone", "manual", "other"] as const;
export type JobSource = (typeof SOURCES)[number];

export const REMOTE_TYPES = ["onsite", "hybrid", "remote", "unknown"] as const;
export type RemoteType = (typeof REMOTE_TYPES)[number];

export type SortField = "created_at" | "updated_at" | "status_changed_at" | "priority" | "title";

export interface Company {
  id: number;
  name: string;
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
  location: string | null;
  remote_type: RemoteType;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  description: string | null;
  posted_at: string | null;
  raw_payload: Record<string, unknown>;
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
  sort: SortField;
  order: "asc" | "desc";
}
