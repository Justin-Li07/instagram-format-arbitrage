import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type FormatMarketRow } from '../api'
import { Async, PageHeader, StatusBadge, asArray, fmtNum, fmtPct, useApi, useNiche } from '../lib'

type SortKey = 'name' | 'price' | 'supply' | 'score' | 'n_creators' | 'n_reels' | 'small_creator_share' | 'status'

const COLS: { key: SortKey; label: string; num?: boolean; title?: string }[] = [
  { key: 'name', label: 'Format' },
  { key: 'price', label: 'Price', num: true, title: 'Median views per reel' },
  { key: 'supply', label: 'Supply / wk', num: true, title: 'New reels per week' },
  { key: 'score', label: 'Score', num: true, title: 'price / (supply + 1)' },
  { key: 'status', label: 'Status' },
  { key: 'n_creators', label: 'Creators', num: true },
  { key: 'n_reels', label: 'Reels', num: true },
  { key: 'small_creator_share', label: 'Small-creator share', num: true },
]

const WEEKS = [4, 8, 12, 26]

export default function FormatsPage() {
  const [niche] = useNiche()
  const [weeks, setWeeks] = useState(8)
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'score', desc: true })
  const [q, setQ] = useState('')
  const state = useApi(() => api.formats({ niche, weeks }), [niche, weeks])
  const nav = useNavigate()

  const rows = useMemo(() => {
    let r = asArray<FormatMarketRow>(state.data)
    if (q.trim()) r = r.filter((x) => (x.name ?? '').toLowerCase().includes(q.trim().toLowerCase()))
    const dir = sort.desc ? -1 : 1
    return [...r].sort((a, b) => {
      const av = a[sort.key] as unknown
      const bv = b[sort.key] as unknown
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir
      return String(av ?? '').localeCompare(String(bv ?? '')) * dir
    })
  }, [state.data, sort, q])

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const r of asArray<FormatMarketRow>(state.data)) c[r.status] = (c[r.status] ?? 0) + 1
    return c
  }, [state.data])

  return (
    <>
      <PageHeader
        title="Format market"
        subtitle="Price = median views per reel. Supply = new reels per week. High price and low supply is the arbitrage."
        right={
          <div className="controls">
            <input className="input" placeholder="Filter formats…" value={q} onChange={(e) => setQ(e.target.value)} />
            <label className="control-label">
              Window
              <select className="input" value={weeks} onChange={(e) => setWeeks(Number(e.target.value))}>
                {WEEKS.map((w) => (
                  <option key={w} value={w}>
                    {w} weeks
                  </option>
                ))}
              </select>
            </label>
          </div>
        }
      />
      <Async state={state} isEmpty={(d) => asArray(d).length === 0}>
        {() => (
          <>
            <div className="stat-row">
              {(['opportunity', 'closing', 'crowded', 'new'] as const).map((s) => (
                <div key={s} className="stat-card">
                  <div className="stat-label">
                    <StatusBadge status={s} />
                  </div>
                  <div className="stat-value">{counts[s] ?? 0}</div>
                </div>
              ))}
            </div>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    {COLS.map((c) => (
                      <th
                        key={c.key}
                        className={`${c.num ? 'num' : ''} sortable ${sort.key === c.key ? 'sorted' : ''}`}
                        title={c.title}
                        onClick={() => setSort((s) => ({ key: c.key, desc: s.key === c.key ? !s.desc : c.num ?? false }))}
                      >
                        {c.label}
                        {sort.key === c.key ? (sort.desc ? ' ▾' : ' ▴') : ''}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={r.id ?? r.name}
                      className="clickable"
                      onClick={() =>
                        nav(`/formats/${r.id}${niche ? `?niche=${niche}` : ''}`, { state: { row: r } })
                      }
                    >
                      <td className="cell-strong" title={r.description ?? undefined}>
                        {r.name}
                        {r.style && <span className="tag">{r.style}</span>}
                      </td>
                      <td className="num">{fmtNum(r.price)}</td>
                      <td className="num">{fmtNum(r.supply)}</td>
                      <td className="num cell-strong">{fmtNum(r.score)}</td>
                      <td>
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="num">{fmtNum(r.n_creators)}</td>
                      <td className="num">{fmtNum(r.n_reels)}</td>
                      <td className="num">{fmtPct(r.small_creator_share)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length === 0 && <div className="state state-empty">No formats match “{q}”.</div>}
            </div>
          </>
        )}
      </Async>
    </>
  )
}
