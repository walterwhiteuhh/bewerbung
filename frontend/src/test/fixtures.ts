import type { CompanyActivity, EmployerRating, JobFeatures, Listing, SearchHit } from "../api/types";

export function features(over: Partial<JobFeatures> = {}): JobFeatures {
  return {
    city: "Hamburg",
    postal_code: "20095",
    region: "Hamburg",
    lat: 53.55,
    lon: 9.99,
    position_estimated: false,
    distance_km: null,
    distance_estimated: false,
    within_max_distance: null,
    age_days: null,
    days_online: null,
    times_seen: 1,
    portals: ["arbeitsagentur"],
    is_repost: false,
    match_score: null,
    matched_skills: [],
    missing_skills: [],
    company: null,
    similar_saved: null,
    ...over,
  };
}

export function company(over: Partial<CompanyActivity> = {}): CompanyActivity {
  return {
    company_id: 1,
    listings: 1,
    active_listings: 1,
    portals: ["arbeitsagentur"],
    website: null,
    social_links: {},
    employer_rating: null,
    saved_postings: 0,
    applications: 0,
    rejections: 0,
    last_status: null,
    ...over,
  };
}

export function rating(over: Partial<EmployerRating> = {}): EmployerRating {
  return {
    mean: 4.1,
    sources: ["glassdoor", "kununu"],
    review_count: 251,
    min_reviews: 10,
    current: [
      { id: 1, source: "kununu", rating: 3.9, raw_value: 3.9, scale_max: 5, review_count: 214, url: null, method: "manual", observed_at: "2026-11-25T10:00:00Z" },
      { id: 2, source: "glassdoor", rating: 4.3, raw_value: 4.3, scale_max: 5, review_count: 37, url: null, method: "manual", observed_at: "2026-11-25T10:00:00Z" },
    ],
    ...over,
  };
}

export function listing(over: Partial<Listing> = {}): Listing {
  return {
    id: 1,
    posting_id: null,
    source: "arbeitsagentur",
    external_id: "a1",
    url: null,
    title: "Data Engineer",
    company_name: "ACME",
    company_logo_url: null,
    location: "Hamburg",
    remote_type: "unknown",
    employment_type: null,
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    description: null,
    posted_at: null,
    first_seen_at: "2026-11-20T10:00:00Z",
    last_seen_at: "2026-11-25T10:00:00Z",
    ...over,
  };
}

export function hit(rank: number, f: Partial<JobFeatures> | null): SearchHit {
  return { rank, is_new: false, listing: listing({ id: rank }), features: f ? features(f) : null };
}
