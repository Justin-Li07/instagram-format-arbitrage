import { useMemo, useState } from 'react'
import { api, type Outlier } from '../api'
import { Async, NLink, PageHeader, ReelLink, asArray, fmtMultiple, fmtNum, useApi, useNiche } from '../lib'

const MULTIPLES = [3, 5, 10, 20, 50]

export default function OutliersPage() {
  const [niche] = useNiche()
  const [minMultiple, setMinMultiple] = useState(10)
  const [smallOnly, setSmallOnly] = useState(false)
  const state = useApi(() => api.outliers({ niche, min_multiple: minMultiple, limit: 200 }), [niche, minMultiple])

  const rows = useMemo(() => {
    const all = asArray<Outlier>(state.data)
    return smallOnly ? all.filter((r) => r.is_small_creator) : all
  }, [state.data, smallOnly])

  return (
    <>
      <PageHeader
        title="Outlier reels"
        subtitle="Reels far above their creator's median. Small creators: under 10K followers with 100K+ views."
        right={
          <div className="controls">
            <label className="toggle">
              <input type="checkbox" checked={smallOnly} onChange={(e) => setSmallOnly(e.target.checked)} />
              <span>Small creators only</span>
            </label>
            <label className="control-label">
              Min ×
              <select className="input" value={minMultiple} onChange={(e) => setMinMultiple(Number(e.target.value))}>
                {MULTIPLES.map((m) => (
                  <option key={m} value={m}>
                    {m}× median
                  </option>
                ))}
              </select>
            </label>
          </div>
        }
      />
      <Async state={state} isEmpty={(d) => asArray(d).length === 0}>
        {() => (
          <div className="table-wrap">
            <div className="table-meta muted">{rows.length} reels</div>
            <table className="table">
              <thead>
                <tr>
                  <th>Creator</th>
                  {!niche && <th>Niche</th>}
                  <th className="num">Followers</th>
                  <th className="num">Views</th>
                  <th className="num">Creator median</th>
                  <th className="num">× median</th>
                  <th>Format</th>
                  <th>Hook</th>
                  <th>Reel</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.code}>
                    <td className="cell-strong">
                      <NLink to={`/creators/${encodeURIComponent(r.creator)}`}>@{r.creator}</NLink>
                      {r.is_small_creator && <span className="tag tag-green">small</span>}
                    </td>
                    {!niche && <td className="muted">{r.niche}</td>}
                    <td className="num">{fmtNum(r.followers)}</td>
                    <td className="num cell-strong">{fmtNum(r.views)}</td>
                    <td className="num muted">{fmtNum(r.creator_median)}</td>
                    <td className="num">
                      <span className="multiple">{fmtMultiple(r.multiple)}</span>
                    </td>
                    <td>{r.format ?? <span className="muted">unlabeled</span>}</td>
                    <td className="cell-hook" title={r.hook ?? undefined}>
                      {r.hook ?? <span className="muted">—</span>}
                    </td>
                    <td>
                      <ReelLink code={r.code} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <div className="state state-empty">No small-creator outliers at this threshold.</div>}
          </div>
        )}
      </Async>
    </>
  )
}
