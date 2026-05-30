import { wmoIcon, wmoLabel, windDir } from '../meteoUtils'

function HourSlot({ hour, isNow }) {
  const d = new Date(hour.time)
  const label = isNow ? 'Maint.' : d.toLocaleTimeString('fr', { hour: '2-digit', minute: '2-digit' })
  const icon = wmoIcon(hour.weathercode)
  const precip = hour.precipitation_probability
  return (
    <div className={`hour-slot${isNow ? ' now' : ''}`}>
      <span className="hour-lbl">{label}</span>
      <i className={`ti ${icon} hour-icon`} />
      <span className="hour-temp">{Math.round(hour.temperature_2m)}°</span>
      {precip > 0
        ? <span className="hour-precip">{precip}%</span>
        : <span className="hour-precip dry">·</span>}
    </div>
  )
}

export default function MeteoCard({ meteo }) {
  if (!meteo) {
    return (
      <div className="meteo-card">
        <div className="meteo-label">Chargement météo…</div>
      </div>
    )
  }

  const cur = meteo.current
  const hourlyTimes = meteo.hourly?.time ?? []
  const now = new Date()

  // Prochaines 24h à partir de maintenant
  const startIdx = hourlyTimes.findIndex(t => new Date(t) >= now)
  const slots = hourlyTimes.slice(startIdx, startIdx + 24).map((t, i) => ({
    time: t,
    temperature_2m: meteo.hourly.temperature_2m[startIdx + i],
    precipitation_probability: meteo.hourly.precipitation_probability[startIdx + i],
    weathercode: meteo.hourly.weathercode[startIdx + i],
  }))

  const daily = meteo.daily
  const tomorrowIdx = 1
  const tomorrowMin = daily?.temperature_2m_min?.[tomorrowIdx]
  const tomorrowMax = daily?.temperature_2m_max?.[tomorrowIdx]
  const tomorrowCode = daily?.weathercode?.[tomorrowIdx]

  // Modèles : best_match et ecmwf
  const aromeMax = daily?.temperature_2m_max?.[tomorrowIdx]
  const ecmwfMax = meteo.daily_units ? null : null // open-meteo renvoie best_match seulement dans cette URL simplifiée

  return (
    <div className="meteo-card">
      <div className="meteo-top">
        <div>
          <div className="meteo-label">Ascain · maintenant</div>
          <span className="meteo-temp">{Math.round(cur.temperature_2m)}°</span>{' '}
          <span className="meteo-cond">{wmoLabel(cur.weathercode)}</span>
          <div className="meteo-details">
            <span className="meteo-detail">
              <i className="ti ti-droplet" style={{ color: '#1D9E75' }} />
              {cur.relative_humidity_2m}%
            </span>
            <span className="meteo-detail">
              <i className="ti ti-wind" />
              {Math.round(cur.wind_speed_10m)} km/h {windDir(cur.wind_direction_10m)}
            </span>
          </div>
        </div>
        <i className={`ti ${wmoIcon(cur.weathercode)}`} style={{ fontSize: 54, color: '#EF9F27', marginTop: -4 }} />
      </div>

      <div className="hourly-strip">
        {slots.map((s, i) => <HourSlot key={s.time} hour={s} isNow={i === 0} />)}
      </div>

      {tomorrowMax != null && (
        <div className="meteo-divider">
          <div className="tomorrow-row">
            <div className="tomorrow-left">
              <i className={`ti ${wmoIcon(tomorrowCode)}`} style={{ fontSize: 18, color: '#378ADD' }} />
              <span style={{ fontSize: 14 }}>
                Demain — {Math.round(tomorrowMin)}° / {Math.round(tomorrowMax)}°
              </span>
            </div>
            <span style={{ fontSize: 12, color: '#8C8880' }}>{wmoLabel(tomorrowCode)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
