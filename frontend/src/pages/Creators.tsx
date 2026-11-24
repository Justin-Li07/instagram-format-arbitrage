import { useMemo, useState } from 'react'
import { api, type CreatorListItem } from '../api'
import { Async, NLink, PageHeader, asArray, fmtDate, fmtNum, useApi, useNiche } from '../lib'

type SortKey = 'username' | 'followers' | 'reel_count' | 'median_views' | 'outlier_count'

export default function CreatorsPage() {
  const [niche] = useNiche()
  const state = useApi(() => api.creators(niche), [niche])
  const [q, setQ] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'followers', desc: true })

  const rows = useMemo(() => {
    let r = asArray<CreatorListItem>(state.data)
    if (q.trim()) r = r.filter((c) => c.username.toLowerCase().includes(q.trim().toLowerCase().replace(/^@/, '')))
    const dir = sort.desc ? -1 : 1
    return [...r].sort((a, b) => {
      const av = a[sort.key]
      const bv = b[sort.key]
      if (typeof av === 'string' || typeof bv === 'string') return String(av ?? '').localeCompare(String(bv ?? '')) * dir
      return ((av ?? -1) - (bv ?? -1)) * dir
    })
  }, [state.data, q, sort])

  const th = (key: SortKey, label: string, num = true) => (
    <th
      className={`${num ? 'num' : ''} sortable ${sort.key === key ? 'sorted' : ''}`}
      onClick={() => setSort((s) => ({ key, desc: s.key === key ? !s.desc : num }))}
    >
      {label}
      {sort.key === key ? (sort.desc ? ' ▾' : ' ▴') : ''}
    </th>
  )

  return (
    <>
      <PageHeader
        title="Creators"
        right={<input className="input" placeholder="Search @username…" value={q} onChange={(e) => setQ(e.target.value)} />}
      />
      <Async state={state} isEmpty={(d) => asArray(d).length === 0}>
        {() => (
          <div className="table-wrap">
            <div className="table-meta muted">{rows.length} creators</div>
            <table className="table">
              <thead>
                <tr>
                  {th('username', 'Creator', false)}
                  {!niche && <th>Niche</th>}
                  {th('followers', 'Followers')}
                  {th('reel_count', 'Reels')}
                  {th('median_views', 'Median views')}
                  {th('outlier_count', 'Outliers')}
                  <th>Last seen</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.username}>
                    <td className="cell-strong">
                      <NLink to={`/creators/${encodeURIComponent(c.username)}`}>@{c.username}</NLink>
                    </td>
                    {!niche && <td className="muted">{c.niche}</td>}
                    <td className="num">{fmtNum(c.followers)}</td>
                    <td className="num">{fmtNum(c.reel_count)}</td>
                    <td className="num">{fmtNum(c.median_views)}</td>
                    <td className="num">{c.outlier_count ? <span className="multiple">{c.outlier_count}</span> : fmtNum(c.outlier_count)}</td>
                    <td className="muted">{fmtDate(c.last_seen_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Async>
    </>
  )
}
