import { useParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type CreatorDetail, type CreatorReel, type FollowerPoint } from '../api'
import {
  Async,
  NLink,
  PageHeader,
  ReelLink,
  asArray,
  chartTheme,
  fmtDate,
  fmtMultiple,
  fmtNum,
  useApi,
} from '../lib'

function ReelTable({ reels }: { reels: CreatorReel[] }) {
  const sorted = [...reels].sort((a, b) => (b.views ?? 0) - (a.views ?? 0))
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Reel</th>
          <th className="num">Views</th>
          <th className="num">× median</th>
          <th>Format</th>
          <th>Hook</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.code}>
            <td>
              <ReelLink code={r.code} />
            </td>
            <td className="num cell-strong">{fmtNum(r.views)}</td>
            <td className="num">
              {r.multiple != null ? <span className={r.multiple >= 10 ? 'multiple' : ''}>{fmtMultiple(r.multiple)}</span> : '—'}
            </td>
            <td>{r.format ?? <span className="muted">—</span>}</td>
            <td className="cell-hook">{r.hook ?? <span className="muted">—</span>}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function CreatorDetailPage() {
  const { username = '' } = useParams()
  const state = useApi(() => api.creator(username), [username])

  return (
    <>
      <div className="crumbs">
        <NLink to="/creators">← Creators</NLink>
      </div>
      <Async state={state} emptyMessage={`No data for @${username}.`}>
        {(c: CreatorDetail) => {
          const history = asArray<FollowerPoint>(c.follower_history)
            .filter((p) => p.followers != null)
            .map((p) => ({ ...p, label: fmtDate(p.scraped_at) }))
          const latest = c.followers ?? history[history.length - 1]?.followers ?? null
          const outliers = asArray<CreatorReel>(c.outlier_reels)
          const reels = asArray<CreatorReel>(c.reels)
          return (
            <>
              <PageHeader
                title={`@${c.username ?? username}`}
                subtitle={
                  <a href={`https://www.instagram.com/${c.username ?? username}/`} target="_blank" rel="noopener noreferrer">
                    instagram.com/{c.username ?? username} ↗
                  </a>
                }
                right={c.niche && <span className="tag">{c.niche}</span>}
              />
              <div className="stat-row">
                <div className="stat-card">
                  <div className="stat-label">Followers</div>
                  <div className="stat-value">{fmtNum(latest)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Reels tracked</div>
                  <div className="stat-value">{fmtNum(c.reel_count)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Median views</div>
                  <div className="stat-value">{fmtNum(c.median_views)}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Outlier reels</div>
                  <div className="stat-value">{outliers.length}</div>
                </div>
              </div>

              <div className="panel">
                <h2>Follower history</h2>
                {history.length === 0 ? (
                  <div className="state state-empty">No follower counts recorded yet.</div>
                ) : history.length === 1 ? (
                  <div className="state state-empty">
                    One snapshot so far ({fmtNum(history[0].followers)} on {history[0].label}). The line appears after the next scan.
                  </div>
                ) : (
                  <div className="chart-box">
                    <ResponsiveContainer width="100%" height={260}>
                      <LineChart data={history} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                        <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
                        <XAxis dataKey="label" stroke={chartTheme.axis} fontSize={12} />
                        <YAxis stroke={chartTheme.axis} fontSize={12} tickFormatter={(v: number) => fmtNum(v)} domain={['auto', 'auto']} />
                        <Tooltip
                          contentStyle={{ background: chartTheme.tooltipBg, border: `1px solid ${chartTheme.tooltipBorder}` }}
                          formatter={(v) => fmtNum(typeof v === 'number' ? v : Number(v))}
                        />
                        <Line type="monotone" dataKey="followers" name="Followers" stroke={chartTheme.price} strokeWidth={2} dot={{ r: 3 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>

              <div className="panel">
                <h2>Outlier reels</h2>
                {outliers.length ? <ReelTable reels={outliers} /> : <div className="state state-empty">No outlier reels.</div>}
              </div>

              {reels.length > 0 && (
                <div className="panel">
                  <h2>All reels</h2>
                  <ReelTable reels={reels} />
                </div>
              )}
            </>
          )
        }}
      </Async>
    </>
  )
}
