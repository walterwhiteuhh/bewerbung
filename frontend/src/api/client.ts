import type {
  Application,
  ImportPreview,
  ProviderInfo,
  SearchParams,
  SearchProfile,
  SearchRun,
  SearchRunSummary,
  Note,
  PostingDetail,
  PostingFilter,
  PostingInput,
  PostingPage,
  SourceDetection,
  Stats,
  ApplicationStatus,
  TagCount,
  Company,
  CompanyUpdate,
  CoverLetter,
  GeneratorInfo,
  LetterContext,
  LetterRequest,
  Profile,
  DocumentInfo,
  DocumentKind,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly body: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI-Validierungsfehler: [{loc, msg}, ...]
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${d.loc?.slice(1).join(".") ?? ""}: ${d.msg ?? ""}`)
      .join("; ");
  }
  return "Unbekannter Fehler";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
  });
  if (!resp.ok) {
    const body = (await resp.json().catch(() => ({}))) as Record<string, unknown>;
    throw new ApiError(resp.status, describe(body.detail) || resp.statusText, body);
  }
  return (await resp.json()) as T;
}

const json = (method: string, data: unknown): RequestInit => ({ method, body: JSON.stringify(data) });

export const api = {
  listPostings(f: PostingFilter, limit = 200): Promise<PostingPage> {
    const params = new URLSearchParams({ sort: f.sort, order: f.order, limit: String(limit) });
    if (f.q.trim()) params.set("q", f.q.trim());
    f.status.forEach((s) => params.append("status", s));
    f.source.forEach((s) => params.append("source", s));
    f.remote.forEach((r) => params.append("remote", r));
    f.tag.forEach((t) => params.append("tag", t));
    if (f.location.trim()) params.set("location", f.location.trim());
    if (f.minSalary !== null) params.set("min_salary", String(f.minSalary));
    if (f.followUpDue) params.set("follow_up_due", "true");
    if (f.includeArchived) params.set("include_archived", "true");
    return request(`/postings?${params}`);
  },
  getPosting: (id: number) => request<PostingDetail>(`/postings/${id}`),
  createPosting: (data: PostingInput) => request<PostingDetail>("/postings", json("POST", data)),
  updatePosting: (id: number, data: Partial<PostingInput>) =>
    request<PostingDetail>(`/postings/${id}`, json("PATCH", data)),
  archivePosting: (id: number) => request<PostingDetail>(`/postings/${id}/archive`, { method: "POST" }),
  restorePosting: (id: number) => request<PostingDetail>(`/postings/${id}/restore`, { method: "POST" }),
  detectSource: (url: string) =>
    request<SourceDetection>(`/sources/detect?${new URLSearchParams({ url })}`),
  importPreview: (url: string) => request<ImportPreview>("/sources/import", json("POST", { url })),
  changeStatus: (appId: number, status: ApplicationStatus, note?: string, occurredAt?: string) =>
    request<Application>(
      `/applications/${appId}/status`,
      json("POST", { status, note: note || null, occurred_at: occurredAt ?? null }),
    ),
  updateApplication: (appId: number, data: Partial<Pick<Application, "priority" | "contact_name" | "contact_email" | "follow_up_at">>) =>
    request<Application>(`/applications/${appId}`, json("PATCH", data)),
  addNote: (appId: number, body: string) => request<Note>(`/applications/${appId}/notes`, json("POST", { body })),
  companies: () => request<Company[]>("/companies"),
  updateCompany: (id: number, data: CompanyUpdate) => request<Company>(`/companies/${id}`, json("PATCH", data)),
  fetchCompanyLogo: (id: number) => request<Company>(`/companies/${id}/logo`, { method: "POST" }),
  stats: () => request<Stats>("/stats"),
  tags: () => request<TagCount[]>("/tags"),
  providers: () => request<ProviderInfo[]>("/search/providers"),
  search: (p: SearchParams) => request<SearchRun>("/search", json("POST", p)),
  searchRuns: () => request<SearchRunSummary[]>("/search/runs?limit=8"),
  searchRun: (id: number) => request<SearchRun>(`/search/runs/${id}`),
  profiles: () => request<SearchProfile[]>("/search/profiles"),
  createProfile: (p: Omit<SearchProfile, "id" | "created_at">) =>
    request<SearchProfile>("/search/profiles", json("POST", p)),
  updateProfile: (id: number, p: Omit<SearchProfile, "id" | "created_at">) =>
    request<SearchProfile>(`/search/profiles/${id}`, json("PUT", p)),
  deleteRun: async (id: number) => {
    const resp = await fetch(`/api/search/runs/${id}`, { method: "DELETE" });
    if (!resp.ok) throw new ApiError(resp.status, "Löschen fehlgeschlagen");
  },
  clearRuns: () => request<{ hidden: number }>("/search/runs", { method: "DELETE" }),
  deleteProfile: async (id: number) => {
    const resp = await fetch(`/api/search/profiles/${id}`, { method: "DELETE" });
    if (!resp.ok) throw new ApiError(resp.status, "Löschen fehlgeschlagen");
  },
  saveListing: (id: number, priority = 3) =>
    request<PostingDetail>(`/listings/${id}/save`, json("POST", { priority })),
  profile: () => request<Profile>("/profile"),
  saveProfile: (p: Omit<Profile, "updated_at">) => request<Profile>("/profile", json("PUT", p)),
  generators: () => request<GeneratorInfo[]>("/letters/generators"),
  letterContext: (postingId: number) => request<LetterContext>(`/postings/${postingId}/letter-context`),
  letters: (postingId: number) => request<CoverLetter[]>(`/postings/${postingId}/letters`),
  generateLetter: (postingId: number, r: LetterRequest) =>
    request<CoverLetter>(`/postings/${postingId}/letters`, json("POST", r)),
  documents: () => request<DocumentInfo[]>("/documents"),
  uploadDocument: async (file: File, kind?: DocumentKind): Promise<DocumentInfo> => {
    const body = new FormData();
    body.append("file", file);
    if (kind) body.append("kind", kind);
    // Kein Content-Type setzen: der Browser ergänzt die multipart-Grenze selbst.
    const resp = await fetch("/api/documents", { method: "POST", body });
    const data = (await resp.json().catch(() => ({}))) as Record<string, unknown>;
    if (!resp.ok) throw new ApiError(resp.status, describe(data.detail) || resp.statusText, data);
    return data as unknown as DocumentInfo;
  },
  updateDocument: (id: number, data: Partial<Pick<DocumentInfo, "kind" | "title" | "is_primary">>) =>
    request<DocumentInfo>(`/documents/${id}`, json("PATCH", data)),
  archiveDocument: (id: number) => request<DocumentInfo>(`/documents/${id}/archive`, { method: "POST" }),
  useDocumentAsCv: (id: number) => request<Profile>(`/documents/${id}/use-as-cv`, { method: "POST" }),
  documentUrl: (id: number, download = false) => `/api/documents/${id}/file${download ? "?download=true" : ""}`,
  postingDocuments: (postingId: number) => request<DocumentInfo[]>(`/postings/${postingId}/documents`),
  setPostingDocuments: (postingId: number, ids: number[]) =>
    request<DocumentInfo[]>(`/postings/${postingId}/documents`, json("PUT", { document_ids: ids })),
  updateLetter: (id: number, data: Partial<Pick<CoverLetter, "body" | "status">>) =>
    request<CoverLetter>(`/letters/${id}`, json("PATCH", data)),
};
