import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link, useSearchParams, type LinkProps } from 'react-router-dom'
import { NICHES, reelUrl, type FormatStatus } from './api'

// ---------- number formatting ----------

export function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const abs = Math.abs(v)
  const trim = (x: number) => x.toFixed(digits).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1')
  if (abs >= 1e9) return `${trim(v / 1e9)}B`
  if (abs >= 1e6) return `${trim(v / 1e6)}M`
  if (abs >= 1e3) return `${trim(v / 1e3)}K`
  if (abs >= 100 || Number.isInteger(v)) return String(Math.round(v))
  return trim(v)
}

export const fmtMultiple = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${v >= 100 ? Math.round(v) : v.toFixed(1)}×`

export const fmtPct = (v: number | null | undefined) =>
  v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`

export function fmtDate(s: string | null | undefined, withTime = false): string {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return withTime
    ? d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

// ---------- niche in URL ----------

export function useNiche(): [string | null, (n: string | null) => void] {
  const [sp, setSp] = useSearchParams()
  const raw = sp.get('niche')
  const niche = raw && (NICHES as readonly string[]).includes(raw) ? raw : null
  const set = useCallback(
    (n: string | null) => {
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (n) next.set('niche', n)
          else next.delete('niche')
          return next
        },
        { replace: true },
      )
    },
    [setSp],
  )
  return [niche, set]
}

/** Link that keeps ?niche= when navigating between pages. */
export function NLink({ to, ...rest }: LinkProps & { to: string }) {
  const [niche] = useNiche()
  const target = niche ? `${to}${to.includes('?') ? '&' : '?'}niche=${encodeURIComponent(niche)}` : to
  return <Link to={target} {...rest} />
}

// ---------- data fetching ----------

export interface AsyncState<T> {
  data: T | undefined
  error: string | null
  loading: boolean
  reload: () => void
}

export function useApi<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(null)
    fn()
      .then((d) => {
        if (alive) setData(d)
      })
      .catch((e: unknown) => {
        if (alive) {
          setData(undefined)
          setError(e instanceof Error ? e.message : String(e))
        }
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  return { data, error, loading, reload: () => setTick((t) => t + 1) }
}

/** Coerce a maybe-array response to an array (degrades gracefully on shape drift). */
export function asArray<T>(v: unknown): T[] {
  if (Array.isArray(v)) return v as T[]
  if (v && typeof v === 'object') {
    for (const key of ['items', 'results', 'data']) {
      const inner = (v as Record<string, unknown>)[key]
      if (Array.isArray(inner)) return inner as T[]
    }
  }
  return []
}

// ---------- UI bits ----------

export function StatusBadge({ status }: { status: FormatStatus | string | null | undefined }) {
  const s = status ?? 'unknown'
  return <span className={`badge badge-${s}`}>{s}</span>
}

export function ReelLink({ code, label }: { code: string; label?: ReactNode }) {
  return (
    <a className="reel-link" href={reelUrl(code)} target="_blank" rel="noopener noreferrer" title={`Open reel ${code}`}>
      {label ?? code} ↗
    </a>
  )
}

export const EMPTY_MSG = 'No data yet: import a scan on the Runs page'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state state-loading">
      <span className="spinner" /> {label}
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="state state-error">
      <strong>Couldn't load data.</strong> <span className="muted">{error}</span>
      {onRetry && (
        <button className="btn btn-small" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function Empty({ message = EMPTY_MSG }: { message?: string }) {
  return (
    <div className="state state-empty">
      {message === EMPTY_MSG ? (
        <>
          No data yet: import a scan on the <NLink to="/runs">Runs page</NLink>
        </>
      ) : (
        message
      )}
    </div>
  )
}

/** Renders loading / error / empty, otherwise children(data). */
export function Async<T>({
  state,
  isEmpty,
  emptyMessage,
  children,
}: {
  state: AsyncState<T>
  isEmpty?: (d: T) => boolean
  emptyMessage?: string
  children: (d: T) => ReactNode
}) {
  if (state.loading && state.data === undefined) return <Loading />
  if (state.error) return <ErrorState error={state.error} onRetry={state.reload} />
  if (state.data === undefined || state.data === null || (isEmpty && isEmpty(state.data)))
    return <Empty message={emptyMessage} />
  return <>{children(state.data)}</>
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: ReactNode; right?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {right && <div className="page-header-right">{right}</div>}
    </div>
  )
}

export const BUCKET_COLORS: Record<string, string> = {
  '<10K': '#22c55e',
  '10–50K': '#38bdf8',
  '50–250K': '#a78bfa',
  '250K–1M': '#f59e0b',
  '1M+': '#f43f5e',
}

export const chartTheme = {
  grid: '#262b36',
  axis: '#8b93a7',
  tooltipBg: '#151922',
  tooltipBorder: '#2d3340',
  price: '#38bdf8',
  supply: '#f59e0b',
}
