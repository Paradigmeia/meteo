import { formatHoverLabel } from '../utils/chartUtils'

export default function SurvolPanel({ releve, period, repos }) {
  const label = formatHoverLabel(new Date(releve.recu_le), period)

  return (
    <div className={`hover-panel${repos ? ' repos' : ''}`}>
      <div className="hover-panel-time">{label}</div>
      <div className="hover-panel-values">
        <span className="hover-panel-temp">
          🌡 {releve.temperature != null ? `${releve.temperature.toFixed(1)}°C` : '—'}
        </span>
        <span className="hover-panel-hum">
          💧 {releve.humidite != null ? `${Math.round(releve.humidite)}%` : '—'}
        </span>
      </div>
    </div>
  )
}
