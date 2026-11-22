
import { useEffect, useState } from 'react'
import './MonitoringPanel.css'

type TrafficPoint = {
  timestamp: number
  requests_per_minute: number
}

type MonitoringData = {
  collected_at: number
  fastapi_up: number | null
  http_5xx_last_5m_estimate: number | null
  request_rate_per_minute: number | null
  history: TrafficPoint[]
}

function TrafficChart({
  points,
}: {
  points: TrafficPoint[]
}) {
  if (points.length < 2) {
    return (
      <p className="monitor-muted">
        Not enough traffic history yet.
      </p>
    )
  }

  const width = 700
  const height = 190
  const padding = 16

  const maxValue = Math.max(
    0.01,
    ...points.map(p => p.requests_per_minute)
  )

  const positions = points.map((point, index) => {
    const x =
      padding +
      (index / (points.length - 1)) *
      (width - padding * 2)

    const y =
      height -
      padding -
      (point.requests_per_minute / maxValue) *
      (height - padding * 2)

    return `${x},${y}`
  }).join(' ')

  return (
    <>
      <svg
        className="traffic-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="FastAPI requests per minute over 30 minutes"
      >
        <line
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke="#40516e"
        />

        <polyline
          points={positions}
          fill="none"
          stroke="#62a4ff"
          strokeWidth="3"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>

      <div className="chart-labels">
        <span>
          {new Date(
            points[0].timestamp * 1000
          ).toLocaleTimeString()}
        </span>
        <span>Requests / minute</span>
        <span>
          {new Date(
            points[points.length - 1].timestamp * 1000
          ).toLocaleTimeString()}
        </span>
      </div>
    </>
  )
}

export default function MonitoringPanel() {
  const [data, setData] = useState<MonitoringData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function loadMonitoring() {
      try {
        const response = await fetch('/api/monitoring')

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const result: MonitoringData = await response.json()

        if (active) {
          setData(result)
          setError('')
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : 'Monitoring unavailable'
          )
        }
      }
    }

    void loadMonitoring()

    // Refresh every 15 seconds
    const timer = setInterval(
      () => void loadMonitoring(),
      15000
    )

    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  const status =
    error ? 'UNKNOWN'
    : data?.fastapi_up === 1 ? 'UP'
    : data?.fastapi_up === 0 ? 'DOWN'
    : 'UNKNOWN'

  return (
    <section className="monitor-panel">
      <div className="monitor-header">
        <div>
          <h2>Live Monitoring</h2>
          <p>Prometheus · Auto-refresh every 15s</p>
        </div>
        <span className="monitor-live">● LIVE METRICS</span>
      </div>

      {error && (
        <p className="monitor-error">
          Unable to refresh monitoring: {error}
        </p>
      )}

      <div className="monitor-stats">
        <div className="monitor-stat">
          <span>FastAPI Scrape</span>
          <strong
            className={
              status === 'UP'
                ? 'monitor-good'
                : 'monitor-warning'
            }
          >
            {status}
          </strong>
        </div>

        <div className="monitor-stat">
          <span>HTTP 5xx / 5 min</span>
          <strong>
            {error
              ? '—'
              : data?.http_5xx_last_5m_estimate ?? 'N/A'}
          </strong>
        </div>

        <div className="monitor-stat">
          <span>Requests / minute</span>
          <strong>
            {error
              ? '—'
              : data?.request_rate_per_minute?.toFixed(2)
                ?? 'N/A'}
          </strong>
        </div>
      </div>

      <div className="monitor-graph">
        <h3>Request Traffic — Last 30 Minutes</h3>
        {error ? (
          <p className="monitor-muted">
            Monitoring data unavailable.
          </p>
        ) : (
          <TrafficChart points={data?.history ?? []} />
        )}
      </div>

      <p className="monitor-footnote">
        UP means Prometheus can scrape FastAPI.
        It does not guarantee all API features are healthy.
      </p>
    </section>
  )
}
