import { BrowserRouter, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { NICHES, api } from './api'
import { useApi, useNiche } from './lib'
import FormatsPage from './pages/Formats'
import FormatDetailPage from './pages/FormatDetail'
import OutliersPage from './pages/Outliers'
import VelocityPage from './pages/Velocity'
import HooksPage from './pages/Hooks'
import CreatorsPage from './pages/Creators'
import CreatorDetailPage from './pages/CreatorDetail'
import RunsPage from './pages/Runs'

const NAV = [
  { to: '/formats', label: 'Formats' },
  { to: '/outliers', label: 'Outliers' },
  { to: '/velocity', label: 'Velocity' },
  { to: '/hooks', label: 'Hooks' },
  { to: '/creators', label: 'Creators' },
  { to: '/runs', label: 'Runs / Import' },
]

function NicheSelector() {
  const [niche, setNiche] = useNiche()
  const options: { value: string | null; label: string }[] = [
    { value: null, label: 'All' },
    ...NICHES.map((n) => ({ value: n, label: n })),
  ]
  return (
    <div className="niche-selector" role="tablist" aria-label="Niche">
      {options.map((o) => (
        <button
          key={o.label}
          role="tab"
          aria-selected={niche === o.value}
          className={`chip ${niche === o.value ? 'chip-active' : ''}`}
          onClick={() => setNiche(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

function BackendStatus() {
  const h = useApi(() => api.health(), [])
  const cls = h.loading ? 'dot-pending' : h.error ? 'dot-down' : 'dot-up'
  const label = h.loading ? 'checking API' : h.error ? 'API offline' : 'API online'
  return (
    <span className="backend-status" title={h.error ?? label}>
      <span className={`dot ${cls}`} /> {label}
    </span>
  )
}

function Shell() {
  const { search } = useLocation()
  const niche = new URLSearchParams(search).get('niche')
  const suffix = niche ? `?niche=${encodeURIComponent(niche)}` : ''
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◆</span> Format Arbitrage
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={`${n.to}${suffix}`} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <BackendStatus />
      </header>
      <div className="subbar">
        <NicheSelector />
      </div>
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to={`/formats${suffix}`} replace />} />
          <Route path="/formats" element={<FormatsPage />} />
          <Route path="/formats/:id" element={<FormatDetailPage />} />
          <Route path="/outliers" element={<OutliersPage />} />
          <Route path="/velocity" element={<VelocityPage />} />
          <Route path="/hooks" element={<HooksPage />} />
          <Route path="/creators" element={<CreatorsPage />} />
          <Route path="/creators/:username" element={<CreatorDetailPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="*" element={<div className="state state-empty">Page not found.</div>} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  )
}
