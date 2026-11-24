import { useMemo, useState } from 'react'
import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { BUCKETS, api, reelUrl, type BucketSummary, type VelocityPoint } from '../api'
import {
  Async,
  BUCKET_COLORS,
  PageHeader,
  asArray,
  chartTheme,
  fmtMultiple,
  fmtNum,
  fmtPct,
  useApi,
  useNiche,
} from '../lib'

type YKey = 'views' | 'multiple'

/** Fixed log-scale range + one tick per power of ten (100, 1K, 10K, ...).
 * Without explicit ticks recharts puts a label at every distinct data value, which overlap. */
function logAxis(values: number[]): { domain: [number, number]; ticks: number[] } {
  if (values.length === 0) return { domain: [1, 10], ticks: [1, 10] }
  let lo = Math.floor(Math.log10(Math.min(...values)))
  let hi = Math.ceil(Math.log10(Math.max(...values)))
  if (hi === lo) hi = lo + 1
  const ticks: number[] = []
  for (let e = lo; e <= hi; e++) ticks.push(10 ** e)
  return { domain: [10 ** lo, 10 ** hi], ticks }
}

interface Pt extends VelocityPoint {
  x: number
  y: number
}

function PointTooltip({ active, payload }: { active?: boolean; payload?: { payload: Pt }[] }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="chart-tooltip">
      <div className="cell-strong">@{p.creator}</div>
      <div>Followers: {fmtNum(p.followers)}</div>
      <div>Views: {fmtNum(p.views)}</div>
      <div>Multiple: {fmtMultiple(p.multiple)}</div>
      <div>Velocity: {p.velocity == null ? '—' : `${fmtNum(p.velocity)}/h`}</div>
      <div className="muted">{p.bucket} · click to open reel</div>
    </div>
  )
}

export default function VelocityPage() {
  const [niche] = useNiche()
  const [yKey, setYKey] = useState<YKey>('views')
  const points = useApi(() => api.velocity(niche), [niche])
  const buckets = useApi(() => api.velocityBuckets(niche), [niche])

  const { byBucket, dropped, xAxis, yAxis } = useMemo(() => {
    const groups: Record<string, Pt[]> = {}
    let dropped = 0
    const xs: number[] = []
    const ys: number[] = []
    for (const p of asArray<VelocityPoint>(points.data)) {
      const x = p.followers ?? 0
      const y = (yKey === 'views' ? p.views : p.multiple) ?? 0
      if (!(x > 0 && y > 0)) {
        dropped++
        continue // log scale can't show 0 / null
      }
      ;(groups[p.bucket] ??= []).push({ ...p, x, y })
      xs.push(x)
      ys.push(y)
    }
    return { byBucket: groups, dropped, xAxis: logAxis(xs), yAxis: logAxis(ys) }
  }, [points.data, yKey])

  const bucketOrder = [...BUCKETS, ...Object.keys(byBucket).filter((b) => !(BUCKETS as string[]).includes(b))]

  return (
    <>
      <PageHeader
        title="Velocity vs following"
        subtitle="Does follower count predict views? Each dot is a reel (log–log)."
        right={
          <div className="segmented">
            {(['views', 'multiple'] as const).map((k) => (
              <button key={k} className={yKey === k ? 'active' : ''} onClick={() => setYKey(k)}>
                {k === 'views' ? 'Views' : '× creator median'}
              </button>
            ))}
          </div>
        }
      />

      {asArray<BucketSummary>(buckets.data).length > 0 &&
        (() => {
          const list = asArray<BucketSummary>(buckets.data)
          const sorted = [...list].sort((a, b) => BUCKETS.indexOf(a.bucket) - BUCKETS.indexOf(b.bucket))
          return (
            <div className="bucket-row">
              {sorted.map((b) => (
                <div key={b.bucket} className="stat-card bucket-card" style={{ borderTopColor: BUCKET_COLORS[b.bucket] ?? '#555' }}>
                  <div className="stat-label">{b.bucket} followers</div>
                  <div className="stat-value">{fmtNum(b.median_views)}</div>
                  <div className="stat-sub">median views</div>
                  <div className="bucket-meta">
                    <span>
                      Outlier rate <strong>{fmtPct(b.outlier_rate)}</strong>
                    </span>
                    {b.n_reels != null && <span>{fmtNum(b.n_reels)} reels</span>}
                  </div>
                  <div className="bucket-top" title={b.top_format ?? undefined}>
                    Top: {b.top_format ?? <span className="muted">—</span>}
                  </div>
                </div>
              ))}
            </div>
          )
        })()}

      <div className="panel">
        <Async state={points} isEmpty={(d) => asArray(d).length === 0}>
          {() => (
            <>
              <div className="chart-box">
                <ResponsiveContainer width="100%" height={460}>
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
                    <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
                    <XAxis
                      type="number"
                      dataKey="x"
                      name="Followers"
                      scale="log"
                      domain={xAxis.domain}
                      ticks={xAxis.ticks}
                      interval={0}
                      allowDataOverflow
                      stroke={chartTheme.axis}
                      fontSize={12}
                      tickFormatter={(v: number) => fmtNum(v)}
                      label={{ value: 'followers (log)', position: 'insideBottom', offset: -18, fill: chartTheme.axis, fontSize: 12 }}
                    />
                    <YAxis
                      type="number"
                      dataKey="y"
                      name={yKey}
                      scale="log"
                      domain={yAxis.domain}
                      ticks={yAxis.ticks}
                      interval={0}
                      allowDataOverflow
                      stroke={chartTheme.axis}
                      fontSize={12}
                      tickFormatter={(v: number) => (yKey === 'views' ? fmtNum(v) : fmtMultiple(v))}
                      label={{
                        value: yKey === 'views' ? 'views (log)' : '× median (log)',
                        angle: -90,
                        position: 'insideLeft',
                        fill: chartTheme.axis,
                        fontSize: 12,
                      }}
                    />
                    <ZAxis range={[28, 28]} />
                    <Tooltip content={<PointTooltip />} cursor={{ strokeDasharray: '3 3', stroke: chartTheme.axis }} />
                    <Legend verticalAlign="top" height={30} />
                    {bucketOrder
                      .filter((b) => byBucket[b]?.length)
                      .map((b) => (
                        <Scatter
                          key={b}
                          name={b}
                          data={byBucket[b]}
                          fill={BUCKET_COLORS[b] ?? '#94a3b8'}
                          fillOpacity={0.75}
                          cursor="pointer"
                          onClick={(p: unknown) => {
                            const code = (p as { code?: string; payload?: { code?: string } })?.payload?.code ??
                              (p as { code?: string })?.code
                            if (code) window.open(reelUrl(code), '_blank', 'noopener,noreferrer')
                          }}
                        />
                      ))}
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              {dropped > 0 && (
                <div className="muted small">
                  {dropped} reel{dropped === 1 ? '' : 's'} hidden (unknown followers or zero {yKey}; can't plot on a log axis).
                </div>
              )}
            </>
          )}
        </Async>
      </div>
    </>
  )
}
