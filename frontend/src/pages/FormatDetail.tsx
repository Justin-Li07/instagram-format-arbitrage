import { useLocation, useParams } from 'react-router-dom'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type FormatMarketRow, type FormatWeek } from '../api'
import {
  Async,
  NLink,
  PageHeader,
  StatusBadge,
  asArray,
  chartTheme,
  fmtDate,
  fmtNum,
  fmtPct,
  useApi,
  useNiche,
} from '../lib'

export default function FormatDetailPage() {
  const { id = '' } = useParams()
  const [niche] = useNiche()
  const loc = useLocation()
  const passed = (loc.state as { row?: FormatMarketRow } | null)?.row
  const ts = useApi(() => api.formatTimeseries(id), [id])
  // Fall back to the market list for the header when the page was opened directly.
  const market = useApi(
    () => (passed ? Promise.resolve([passed]) : api.formats({ niche })),
    [niche, id, passed ? 1 : 0],
  )
  const row = asArray<FormatMarketRow>(market.data).find((r) => String(r.id) === id) ?? passed

  return (
    <>
      <div className="crumbs">
        <NLink to="/formats">← Formats</NLink>
      </div>
      <PageHeader
        title={row?.name ?? `Format #${id}`}
        subtitle={row?.description ?? 'Weekly price (median views) and supply (new posts).'}
        right={row && <StatusBadge status={row.status} />}
      />
      {row && (
        <div className="stat-row">
          <Stat label="Price" value={fmtNum(row.price)} />
          <Stat label="Supply / wk" value={fmtNum(row.supply)} />
          <Stat label="Score" value={fmtNum(row.score)} />
          <Stat label="Creators" value={fmtNum(row.n_creators)} />
          <Stat label="Reels" value={fmtNum(row.n_reels)} />
          <Stat label="Small-creator share" value={fmtPct(row.small_creator_share)} />
        </div>
      )}
      <div className="panel">
        <h2>Weekly price vs supply</h2>
        <Async state={ts} isEmpty={(d) => asArray(d).length === 0} emptyMessage="No weekly history for this format yet.">
          {(d) => {
            const data = asArray<FormatWeek>(d).map((w) => ({ ...w, label: fmtDate(w.week) }))
            return (
              <div className="chart-box">
                <ResponsiveContainer width="100%" height={340}>
                  <LineChart data={data} margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                    <CartesianGrid stroke={chartTheme.grid} strokeDasharray="3 3" />
                    <XAxis dataKey="label" stroke={chartTheme.axis} fontSize={12} />
                    <YAxis
                      yAxisId="price"
                      stroke={chartTheme.price}
                      fontSize={12}
                      tickFormatter={(v: number) => fmtNum(v)}
                      label={{ value: 'median views', angle: -90, position: 'insideLeft', fill: chartTheme.price, fontSize: 11 }}
                    />
                    <YAxis
                      yAxisId="supply"
                      orientation="right"
                      stroke={chartTheme.supply}
                      fontSize={12}
                      allowDecimals={false}
                      label={{ value: 'new posts', angle: 90, position: 'insideRight', fill: chartTheme.supply, fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{ background: chartTheme.tooltipBg, border: `1px solid ${chartTheme.tooltipBorder}` }}
                      formatter={(v) => fmtNum(typeof v === 'number' ? v : Number(v))}
                    />
                    <Legend />
                    <Line
                      yAxisId="price"
                      type="monotone"
                      dataKey="median_views"
                      name="Price (median views)"
                      stroke={chartTheme.price}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      connectNulls
                    />
                    <Line
                      yAxisId="supply"
                      type="monotone"
                      dataKey="new_posts"
                      name="Supply (new posts)"
                      stroke={chartTheme.supply}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )
          }}
        </Async>
      </div>
    </>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  )
}
