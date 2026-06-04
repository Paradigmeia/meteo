import { useState } from 'react'
import { useReleves } from '../hooks/useReleves'
import HistoriqueChart from './HistoriqueChart'
import { formatAgo } from '../meteoUtils'

const PERIODS = ['24h', '7d', '30d']

export default function Detail({ slug, nom, onBack }) {
  const [period, setPeriod] = useState('24h')
  const { releves } = useReleves(slug, period)

  const lastTemp = [...releves].reverse().find(r => r.temperature != null)
  const lastHum  = [...releves].reverse().find(r => r.humidite != null)
  const lastAny  = releves[releves.length - 1]

  return (
    <>
      <button className="back-btn" onClick={onBack}>
        <i className="ti ti-arrow-left" />
        Retour
      </button>

      <div className="header-title" style={{ marginBottom: '1.5rem' }}>{nom}</div>

      <div className="metrics">
        <div className="metric">
          <div className="metric-label">Température</div>
          <div className="metric-val" style={{ color: '#BA7517' }}>
            {lastTemp ? `${lastTemp.temperature.toFixed(1)}°` : '—'}
          </div>
        </div>
        <div className="metric">
          <div className="metric-label">Humidité</div>
          <div className="metric-val" style={{ color: '#1D9E75' }}>
            {lastHum ? `${lastHum.humidite}%` : '—'}
          </div>
        </div>
      </div>

      {lastAny && (
        <p style={{ fontSize: 12, color: '#B5B0A8', marginBottom: '1rem' }}>
          Dernière mesure {formatAgo(lastAny.recu_le)}
        </p>
      )}

      <div className="periods">
        {PERIODS.map(p => (
          <button
            key={p}
            className={`period-btn${period === p ? ' active' : ''}`}
            onClick={() => setPeriod(p)}
          >
            {p}
          </button>
        ))}
      </div>

      <div className="chart-card">
        <div className="chart-legend">
          <span className="legend-item"><span style={{ width: 20, height: 2, background: '#BA7517', display: 'inline-block', borderRadius: 1 }} />Température</span>
          <span className="legend-item"><span style={{ width: 20, height: 2, background: '#1D9E75', display: 'inline-block', borderRadius: 1, borderTop: '2px dashed #1D9E75' }} />Humidité</span>
        </div>
        <HistoriqueChart releves={releves} period={period} />
      </div>
    </>
  )
}
