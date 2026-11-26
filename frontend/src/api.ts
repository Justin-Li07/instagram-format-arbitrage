// Typed API client. Field names follow CONTRACT.md exactly. Where the contract
// did not pin a field down, it is marked "assumed" and typed as optional/nullable
// so the UI degrades gracefully if the backend differs.

export const NICHES = ['engineering', 'university-life', 'startups-tech', 'growth-viral'] as const
export type Niche = (typeof NICHES)[number]

export type FormatStatus = 'opportunity' | 'crowded' | 'closing' | 'new'
export type FollowerBucket = '<10K' | '10–50K' | '50–250K' | '250K–1M' | '1M+'
export const BUCKETS: FollowerBucket[] = ['<10K', '10–50K', '50–250K', '250K–1M', '1M+']

// ---------- response types ----------

export interface Health {
  status?: string // assumed, e.g. "ok"
  [k: string]: unknown
}

/** GET /api/niches */
export interface NicheSummary {
  niche: string
  creators: number
  reels: number
  last_scraped_at: string | null
}

/** GET /api/runs, POST /api/ingest/scan (ScrapeRun) */
export interface ScrapeRun {
  id: number
  niche: string
  source: string
  started_at: string
  creators_count: number
  reels_count: number
}

/** GET /api/outliers (find_outliers) */
export interface Outlier {
  views_per_follower?: number | null
  views_tier?: string | null
  follower_tier?: string | null
  sweet_spot?: boolean | null
  code: string
  url: string
  creator: string
  niche: string
  followers: number | null
  views: number
  creator_median: number
  multiple: number
  is_small_creator: boolean
  format: string | null
  hook: string | null
}

/** GET /api/formats (format_market) */
export interface FormatMarketRow {
  id: number // assumed: Format.id, needed for /timeseries
  name: string // assumed: Format.name
  description?: string | null // assumed
  style?: string | null // assumed
  price: number
  supply: number
  n_reels: number
  n_creators: number
  small_creator_share: number
  score: number
  status: FormatStatus
}

/** GET /api/formats/{id}/timeseries */
export interface FormatWeek {
  week: string
  median_views: number | null
  new_posts: number
}

/** GET /api/velocity (velocity_vs_followers) */
export interface VelocityPoint {
  followers: number | null
  views: number
  multiple: number | null
  velocity: number | null
  code: string
  creator: string
  bucket: FollowerBucket
}

/** GET /api/velocity/buckets (bucket_summary) */
export interface BucketSummary {
  bucket: FollowerBucket
  median_views: number | null
  outlier_rate: number // assumed 0..1
  top_format: string | null // assumed name
  n_reels?: number // assumed
}

/** GET /api/hooks (top_hooks) */
export interface TopHook {
  hook: string // assumed key name
  format: string | null
  views: number
  multiple: number
  code?: string // assumed
  creator?: string // assumed
}

/** GET /api/hooks/similar */
export interface SimilarHook {
  code: string // assumed
  hook: string // assumed
  format: string | null // assumed
  similarity?: number // assumed cosine (falls back to `score`)
  score?: number
  views?: number
  creator?: string
}

/** GET /api/creators (list_creators) — fields assumed */
export interface CreatorListItem {
  username: string
  niche: string
  followers: number | null
  reel_count?: number
  median_views?: number | null
  outlier_count?: number
  last_seen_at?: string | null
}

export interface FollowerPoint {
  scraped_at: string
  followers: number | null
}

export interface CreatorReel {
  code: string
  views: number
  multiple?: number | null
  format?: string | null
  hook?: string | null
  url?: string
}

/** GET /api/creators/{username} (creator_summary) */
export interface CreatorDetail {
  username: string
  niche?: string
  followers?: number | null
  follower_history: FollowerPoint[]
  reel_count: number
  median_views: number | null // assumed key for "median"
  outlier_reels: CreatorReel[]
  reels?: CreatorReel[] // assumed: all reels, if provided
}

export interface ReelSnapshotOut {
  scraped_at: string
  views: number
  likes: number | null
  comments: number | null
}

/** GET /api/reels/{code} */
export interface ReelDetail {
  code: string
  url?: string
  caption: string | null
  duration_s: number | null
  posted_at: string | null
  creator: { username: string; niche?: string; followers?: number | null } | string
  snapshots: ReelSnapshotOut[]
  label: {
    format: string | null
    hook_text: string | null
    on_screen: string | null
    style: string | null
  } | null
}

// ---------- request types ----------

/** One raw scraper line, see CONTRACT "Raw input format" */
export interface RawScanRecord {
  u: string
  f: string | null
  r: string[]
}

export interface IngestScanRequest {
  niche: string
  scraped_at?: string
  records: RawScanRecord[]
}

export interface LabelRecord {
  code: string
  format: string
  hook: string
  caption?: string | null
  duration_s?: number | null
  on_screen?: string | null
  style?: string | null
  posted_at?: string | null
}

// ---------- fetch helpers ----------

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the backend (is uvicorn running on :8000?)')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON body (e.g. proxy error) */
    }
    if (res.status === 502 || res.status === 503 || res.status === 504 || (res.status === 500 && !detail)) {
      detail = 'Backend unavailable (is uvicorn running on :8000?)'
    }
    throw new ApiError(res.status, `${res.status} ${detail}`)
  }
  const text = await res.text()
  if (!text) return undefined as T
  try {
    return JSON.parse(text) as T
  } catch {
    throw new ApiError(res.status, 'Backend returned non-JSON (is the API running behind the /api proxy?)')
  }
}

const n = (niche?: string | null) => (niche && niche !== 'all' ? niche : undefined)

export const api = {
  health: () => request<Health>('/health'),
  niches: () => request<NicheSummary[]>('/niches'),
  runs: () => request<ScrapeRun[]>('/runs'),
  ingestScan: (body: IngestScanRequest) =>
    request<ScrapeRun>('/ingest/scan', { method: 'POST', body: JSON.stringify(body) }),
  ingestLabels: (records: LabelRecord[]) =>
    request<unknown>('/ingest/labels', { method: 'POST', body: JSON.stringify({ records }) }),
  breakouts: (p: { niche?: string | null; limit?: number }) =>
    request<Outlier[]>(`/breakouts${qs({ niche: n(p.niche), limit: p.limit })}`),
  outliers: (p: { niche?: string | null; min_multiple?: number; limit?: number }) =>
    request<Outlier[]>(`/outliers${qs({ niche: n(p.niche), min_multiple: p.min_multiple, limit: p.limit })}`),
  formats: (p: { niche?: string | null; weeks?: number }) =>
    // Backend sends format_id/format; map them to the id/name the UI uses.
    request<(FormatMarketRow & { format_id?: number; format?: string })[]>(
      `/formats${qs({ niche: n(p.niche), weeks: p.weeks })}`,
    ).then((rows) => rows.map((r) => ({ ...r, id: r.format_id ?? r.id, name: r.format ?? r.name }))),
  formatTimeseries: (id: number | string) =>
    request<FormatWeek[]>(`/formats/${encodeURIComponent(String(id))}/timeseries`),
  velocity: (niche?: string | null) => request<VelocityPoint[]>(`/velocity${qs({ niche: n(niche) })}`),
  velocityBuckets: (niche?: string | null) =>
    request<BucketSummary[]>(`/velocity/buckets${qs({ niche: n(niche) })}`),
  hooks: (niche?: string | null) => request<TopHook[]>(`/hooks${qs({ niche: n(niche) })}`),
  similarHooks: (p: { text?: string; code?: string; k?: number }) =>
    request<SimilarHook[]>(`/hooks/similar${qs({ text: p.text, code: p.code, k: p.k })}`),
  creators: (niche?: string | null) => request<CreatorListItem[]>(`/creators${qs({ niche: n(niche) })}`),
  creator: (username: string) => request<CreatorDetail>(`/creators/${encodeURIComponent(username)}`),
  reel: (code: string) => request<ReelDetail>(`/reels/${encodeURIComponent(code)}`),
}

export const reelUrl = (code: string) => `https://www.instagram.com/reel/${code}/`
