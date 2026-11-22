
import { useCallback, useEffect, useState } from 'react'
import './App.css'
import MonitoringPanel from './MonitoringPanel'

type Incident = {
  id: string
  fingerprint: string
  alertname: string
  severity: string
  status: string
  summary: string | null
  created_at: string
  resolved_at: string | null
}

type Investigation = {
  incident_id: string
  status: string
  monitoring?: {
    fastapi_up?: number | null
    http_5xx_last_5m_estimate?: number | null
  }
  logs?: {
    status?: string
    entries?: string[]
  }
  analysis: string
  note?: string
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString() : '—'
}

function App() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [report, setReport] = useState<Investigation | null>(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [analysisError, setAnalysisError] = useState('')

  const loadIncidents = useCallback(async () => {
    setLoading(true)

    try {
      const response = await fetch('/api/incidents')

      if (!response.ok) {
        throw new Error(`Backend returned HTTP ${response.status}`)
      }

      const data: { incidents: Incident[] } = await response.json()

      setIncidents(data.incidents)
      setSelectedId(current =>
        data.incidents.some(item => item.id === current)
          ? current
          : data.incidents[0]?.id ?? null
      )
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'API error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadIncidents()
  }, [loadIncidents])

  const selected = incidents.find(item => item.id === selectedId)
  const openCount = incidents.filter(item => item.status === 'open').length
  const resolvedCount = incidents.filter(item => item.status === 'resolved').length

  async function runInvestigation() {
    if (!selectedId) return

    setAnalyzing(true)
    setAnalysisError('')
    setReport(null)

    try {
      const response = await fetch(
        `/api/incidents/${selectedId}/investigate-verified`,
        { method: 'POST' }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      setReport(data as Investigation)
    } catch (err) {
      setAnalysisError(
        err instanceof Error ? err.message : 'Investigation failed'
      )
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">A</div>
          <div>
            <strong>AIOPS CONTROL</strong>
            <span>AI Incident Response Platform</span>
          </div>
        </div>
        <span className="local-tag">● LOCAL ENVIRONMENT</span>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">OPERATIONS / MONITORING</p>
          <h1>Incident Command Center</h1>
          <p className="subtitle">
            Monitor incidents and investigate problems using local AI.
          </p>
        </div>

        <button
          className="secondary-button"
          onClick={() => void loadIncidents()}
          disabled={loading}
        >
          {loading ? 'Loading...' : '↻ Refresh'}
        </button>
      </section>

      {error && <div className="error-box">{error}</div>}

      <section className="stats">
        <article className="stat-card">
          <span>Total Incidents</span>
          <strong>{incidents.length}</strong>
          <small>PostgreSQL records</small>
        </article>

        <article className="stat-card">
          <span>Open Incidents</span>
          <strong className="warning-text">{openCount}</strong>
          <small>Require attention</small>
        </article>

        <article className="stat-card">
          <span>Resolved Incidents</span>
          <strong className="success-text">{resolvedCount}</strong>
          <small>Marked as resolved</small>
        </article>
      </section>

      <MonitoringPanel />

      <section className="workspace">
        <div className="panel incident-panel">
          <div className="panel-heading">
            <h2>Incident Queue</h2>
            <span>{incidents.length} records</span>
          </div>

          {loading && <p className="muted">Loading...</p>}

          {!loading && incidents.length === 0 && (
            <p className="muted">No incidents found.</p>
          )}

          <div className="incident-list">
            {incidents.map(incident => (
              <button
                key={incident.id}
                className={`incident-item ${
                  selectedId === incident.id ? 'selected' : ''
                }`}
                onClick={() => {
                  setSelectedId(incident.id)
                  setReport(null)
                  setAnalysisError('')
                }}
              >
                <div className="incident-top">
                  <strong>{incident.alertname}</strong>
                  <span className={`status ${incident.status}`}>
                    {incident.status}
                  </span>
                </div>

                <p>{incident.summary || 'No summary available'}</p>

                <div className="incident-meta">
                  <span>{incident.severity.toUpperCase()}</span>
                  <span>{formatDate(incident.created_at)}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="panel details-panel">
          <div className="panel-heading">
            <h2>Incident Details</h2>
            <span>PostgreSQL</span>
          </div>

          {selected ? (
            <>
              <h3>{selected.alertname}</h3>
              <p className="detail-summary">{selected.summary}</p>

              <div className="detail-grid">
                <div>
                  <span>Severity</span>
                  <strong>{selected.severity}</strong>
                </div>
                <div>
                  <span>Status</span>
                  <strong>{selected.status}</strong>
                </div>
                <div>
                  <span>Created</span>
                  <strong>{formatDate(selected.created_at)}</strong>
                </div>
                <div>
                  <span>Resolved</span>
                  <strong>{formatDate(selected.resolved_at)}</strong>
                </div>
              </div>

              <p className="fingerprint">
                Fingerprint: {selected.fingerprint}
              </p>

              <button
                className="primary-button"
                onClick={() => void runInvestigation()}
                disabled={analyzing}
              >
                {analyzing
                  ? 'Investigating...'
                  : '✦ Run AI Investigation'}
              </button>

              <p className="help-text">
                Powered by LangGraph, Prometheus and local Ollama.
              </p>

              {analysisError && (
                <div className="error-box">{analysisError}</div>
              )}

              {report && (
                <section className="report">
                  <h3>AI Investigation Report</h3>

                  <div className="evidence">
                    <div>
                      <span>FastAPI near incident</span>
                      <strong>
                        {report.monitoring?.fastapi_up ?? 'N/A'}
                      </strong>
                    </div>

                    <div>
                      <span>5xx near incident</span>
                      <strong>
                        {report.monitoring?.http_5xx_last_5m_estimate ?? 'N/A'}
                      </strong>
                    </div>
                  </div>

                  <pre className="analysis-text">
                    {report.analysis}
                  </pre>

                  <h4>Timestamp-matched Incident Logs</h4>
                  <div className="log-output">
                    {report.logs?.entries?.length
                      ? report.logs.entries.join('\n')
                      : 'No matching recent logs'}
                  </div>

                  <p className="disclaimer">
                    {report.note || 'AI analysis requires human verification.'}
                  </p>
                </section>
              )}
            </>
          ) : (
            <p className="muted">Select an incident.</p>
          )}
        </div>
      </section>
    </main>
  )
}

export default App
