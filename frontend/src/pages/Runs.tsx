import { useMemo, useState } from 'react'
import { NICHES, api, type LabelRecord, type NicheSummary, type RawScanRecord, type ScrapeRun } from '../api'
import { Async, PageHeader, asArray, fmtDate, fmtNum, useApi, useNiche } from '../lib'

type Mode = 'scan' | 'labels'

function parseJsonl<T>(text: string): { records: T[]; errors: string[] } {
  const records: T[] = []
  const errors: string[] = []
  text.split(/\r?\n/).forEach((line, i) => {
    const s = line.trim()
    if (!s) return
    try {
      records.push(JSON.parse(s) as T)
    } catch {
      errors.push(`Line ${i + 1}: not valid JSON`)
    }
  })
  return { records, errors }
}

function validateScan(r: RawScanRecord[]): string[] {
  const errs: string[] = []
  r.forEach((x, i) => {
    if (!x || typeof x.u !== 'string' || !Array.isArray(x.r)) errs.push(`Record ${i + 1}: needs "u" (string) and "r" (array)`)
  })
  return errs
}

function validateLabels(r: LabelRecord[]): string[] {
  const errs: string[] = []
  r.forEach((x, i) => {
    if (!x || typeof x.code !== 'string' || typeof x.format !== 'string') errs.push(`Record ${i + 1}: needs "code" and "format"`)
  })
  return errs
}

export default function RunsPage() {
  const [niche] = useNiche()
  const runs = useApi(() => api.runs(), [])
  const niches = useApi(() => api.niches(), [])

  const [mode, setMode] = useState<Mode>('scan')
  const [target, setTarget] = useState<string>(niche ?? NICHES[0])
  const [scrapedAt, setScrapedAt] = useState('')
  const [text, setText] = useState('')
  const [submit, setSubmit] = useState<{ busy: boolean; ok: string | null; error: string | null }>({ busy: false, ok: null, error: null })

  const parsed = useMemo(() => {
    const p = parseJsonl<RawScanRecord & LabelRecord>(text)
    const v = mode === 'scan' ? validateScan(p.records) : validateLabels(p.records)
    return { records: p.records, errors: [...p.errors, ...v] }
  }, [text, mode])

  const filteredRuns = useMemo(() => {
    const all = asArray<ScrapeRun>(runs.data)
    const r = niche ? all.filter((x) => x.niche === niche) : all
    return [...r].sort((a, b) => String(b.started_at).localeCompare(String(a.started_at)))
  }, [runs.data, niche])

  const onImport = async () => {
    setSubmit({ busy: true, ok: null, error: null })
    try {
      if (mode === 'scan') {
        const run = await api.ingestScan({
          niche: target,
          scraped_at: scrapedAt ? new Date(scrapedAt).toISOString() : undefined,
          records: parsed.records,
        })
        setSubmit({
          busy: false,
          ok: run
            ? `Imported run #${run.id}: ${fmtNum(run.creators_count)} creators, ${fmtNum(run.reels_count)} reels.`
            : 'Imported.',
          error: null,
        })
      } else {
        const res = await api.ingestLabels(parsed.records)
        const count =
          typeof res === 'number'
            ? res
            : res && typeof res === 'object'
              ? ((res as Record<string, unknown>).count ?? (res as Record<string, unknown>).labeled ?? (res as Record<string, unknown>).imported)
              : undefined
        setSubmit({ busy: false, ok: `Imported ${count ?? parsed.records.length} labels.`, error: null })
      }
      setText('')
      runs.reload()
      niches.reload()
    } catch (e) {
      setSubmit({ busy: false, ok: null, error: e instanceof Error ? e.message : String(e) })
    }
  }

  const canImport = !submit.busy && parsed.records.length > 0 && parsed.errors.length === 0

  return (
    <>
      <PageHeader title="Runs / Import" subtitle="Every scrape is stored as history. Paste scraper output to add a new run." />

      <Async state={niches} isEmpty={(d) => asArray(d).length === 0} emptyMessage="No niches imported yet.">
        {(d) => (
          <div className="stat-row">
            {asArray<NicheSummary>(d).map((n) => (
              <div key={n.niche} className={`stat-card ${n.niche === niche ? 'stat-card-active' : ''}`}>
                <div className="stat-label">{n.niche}</div>
                <div className="stat-value">{fmtNum(n.reels)}</div>
                <div className="stat-sub">
                  reels · {fmtNum(n.creators)} creators
                </div>
                <div className="stat-sub muted">last scan {fmtDate(n.last_scraped_at)}</div>
              </div>
            ))}
          </div>
        )}
      </Async>

      <div className="grid-2">
        <div className="panel">
          <div className="panel-head">
            <h2>Import</h2>
            <div className="segmented">
              <button className={mode === 'scan' ? 'active' : ''} onClick={() => setMode('scan')}>
                Scan lines
              </button>
              <button className={mode === 'labels' ? 'active' : ''} onClick={() => setMode('labels')}>
                Label lines
              </button>
            </div>
          </div>
          {mode === 'scan' && (
            <div className="controls form-row">
              <label className="control-label">
                Niche
                <select className="input" value={target} onChange={(e) => setTarget(e.target.value)}>
                  {NICHES.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
              <label className="control-label">
                Scraped at
                <input className="input" type="datetime-local" value={scrapedAt} onChange={(e) => setScrapedAt(e.target.value)} />
              </label>
              <span className="muted small">blank = now</span>
            </div>
          )}
          <textarea
            className="input textarea"
            spellCheck={false}
            placeholder={
              mode === 'scan'
                ? '{"u":"steph.osmak","f":"107K","r":["DdKD20tJSfr 34.4M","Db3uZ4Hpocf 55.8K"]}\n…one creator per line'
                : '{"code":"DeGHQ_CuBFv","format":"Text-over-B-roll + caption list","hook":"…","style":"text-over-broll"}\n…one reel per line'
            }
            value={text}
            onChange={(e) => {
              setText(e.target.value)
              setSubmit((s) => ({ ...s, ok: null, error: null }))
            }}
          />
          <div className="import-foot">
            <span className="muted small">
              {parsed.records.length} {mode === 'scan' ? 'creator' : 'label'} line{parsed.records.length === 1 ? '' : 's'} parsed
            </span>
            <button className="btn" disabled={!canImport} onClick={onImport}>
              {submit.busy ? 'Importing…' : mode === 'scan' ? `Import into ${target}` : 'Import labels'}
            </button>
          </div>
          {parsed.errors.length > 0 && (
            <ul className="error-list">
              {parsed.errors.slice(0, 8).map((e) => (
                <li key={e}>{e}</li>
              ))}
              {parsed.errors.length > 8 && <li>…and {parsed.errors.length - 8} more</li>}
            </ul>
          )}
          {submit.ok && <div className="notice notice-ok">{submit.ok}</div>}
          {submit.error && <div className="notice notice-error">Import failed: {submit.error}</div>}
        </div>

        <div className="panel">
          <h2>Scrape history</h2>
          <Async state={runs} isEmpty={(d) => asArray(d).length === 0} emptyMessage="No runs yet. Paste a scan on the left to create one.">
            {() =>
              filteredRuns.length === 0 ? (
                <div className="state state-empty">No runs for {niche}.</div>
              ) : (
                <table className="table">
                  <thead>
                    <tr>
                      <th className="num">#</th>
                      <th>Niche</th>
                      <th>Started</th>
                      <th className="num">Creators</th>
                      <th className="num">Reels</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRuns.map((r) => (
                      <tr key={r.id}>
                        <td className="num muted">{r.id}</td>
                        <td>{r.niche}</td>
                        <td>{fmtDate(r.started_at, true)}</td>
                        <td className="num">{fmtNum(r.creators_count)}</td>
                        <td className="num">{fmtNum(r.reels_count)}</td>
                        <td className="cell-source" title={r.source}>
                          {r.source.split(/[\\/]/).pop()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            }
          </Async>
        </div>
      </div>
    </>
  )
}
