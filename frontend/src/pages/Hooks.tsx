import { useState, type FormEvent } from 'react'
import { api, type SimilarHook, type TopHook } from '../api'
import {
  Async,
  ErrorState,
  Loading,
  NLink,
  PageHeader,
  ReelLink,
  asArray,
  fmtMultiple,
  fmtNum,
  useApi,
  useNiche,
} from '../lib'

export default function HooksPage() {
  const [niche] = useNiche()
  const top = useApi(() => api.hooks(niche), [niche])

  const [text, setText] = useState('')
  const [sim, setSim] = useState<{ loading: boolean; error: string | null; data: SimilarHook[] | null; query: string }>({
    loading: false,
    error: null,
    data: null,
    query: '',
  })

  const runSearch = async (query: { text?: string; code?: string }, label: string) => {
    setSim({ loading: true, error: null, data: null, query: label })
    try {
      const d = await api.similarHooks({ ...query, k: 15 })
      setSim({ loading: false, error: null, data: asArray<SimilarHook>(d), query: label })
    } catch (e) {
      setSim({ loading: false, error: e instanceof Error ? e.message : String(e), data: null, query: label })
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (text.trim()) runSearch({ text: text.trim() }, text.trim())
  }

  return (
    <>
      <PageHeader title="Hooks" subtitle="Opening lines of outlier reels, plus semantic search for similar hooks." />

      <div className="panel">
        <h2>Find similar hooks</h2>
        <form className="search-row" onSubmit={onSubmit}>
          <input
            className="input input-grow"
            placeholder='e.g. "x engineering certifications you can start TONIGHT"'
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button className="btn" type="submit" disabled={!text.trim() || sim.loading}>
            Search
          </button>
        </form>
        {sim.loading && <Loading label="Searching…" />}
        {sim.error && <ErrorState error={sim.error} />}
        {sim.data && sim.data.length === 0 && <div className="state state-empty">No similar hooks found.</div>}
        {sim.data && sim.data.length > 0 && (
          <table className="table">
            <thead>
              <tr>
                <th className="num">Similarity</th>
                <th>Hook</th>
                <th>Format</th>
                <th className="num">Views</th>
                <th>Reel</th>
              </tr>
            </thead>
            <tbody>
              {sim.data.map((h, i) => {
                const s = h.similarity ?? h.score
                return (
                  <tr key={`${h.code}-${i}`}>
                    <td className="num">
                      {s == null ? '—' : (
                        <span className="sim">
                          <span className="sim-bar" style={{ width: `${Math.max(0, Math.min(1, s)) * 100}%` }} />
                          {s.toFixed(2)}
                        </span>
                      )}
                    </td>
                    <td className="cell-hook">{h.hook}</td>
                    <td>{h.format ?? <span className="muted">—</span>}</td>
                    <td className="num">{fmtNum(h.views)}</td>
                    <td>{h.code && <ReelLink code={h.code} />}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel">
        <h2>Top hooks from outlier reels</h2>
        <Async state={top} isEmpty={(d) => asArray(d).length === 0}>
          {(d) => (
            <table className="table">
              <thead>
                <tr>
                  <th>Hook</th>
                  <th>Format</th>
                  <th>Creator</th>
                  <th className="num">Views</th>
                  <th className="num">× median</th>
                  <th>Reel</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {asArray<TopHook>(d).map((h, i) => (
                  <tr key={`${h.code ?? i}-${i}`}>
                    <td className="cell-hook cell-strong">{h.hook}</td>
                    <td>{h.format ?? <span className="muted">—</span>}</td>
                    <td>
                      {h.creator ? <NLink to={`/creators/${encodeURIComponent(h.creator)}`}>@{h.creator}</NLink> : '—'}
                    </td>
                    <td className="num">{fmtNum(h.views)}</td>
                    <td className="num">
                      <span className="multiple">{fmtMultiple(h.multiple)}</span>
                    </td>
                    <td>{h.code && <ReelLink code={h.code} />}</td>
                    <td>
                      <button
                        className="btn btn-small btn-ghost"
                        onClick={() => {
                          setText(h.hook)
                          if (h.code) runSearch({ code: h.code }, h.hook)
                          else runSearch({ text: h.hook }, h.hook)
                          window.scrollTo({ top: 0, behavior: 'smooth' })
                        }}
                      >
                        Similar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Async>
      </div>
    </>
  )
}
