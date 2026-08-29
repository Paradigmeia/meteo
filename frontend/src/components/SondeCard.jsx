import { formatAgo, isOffline } from '../meteoUtils'
import Icon from './Icon'

function humAgo(dr) {
  if (!dr?.recu_le_hum || !dr?.recu_le) return null
  const diffMs = new Date(dr.recu_le).getTime() - new Date(dr.recu_le_hum).getTime()
  if (diffMs < 30 * 60 * 1000) return null
  return formatAgo(dr.recu_le_hum)
}

export default function SondeCard({ sonde, fullWidth, onClick }) {
  const dr = sonde.dernier_releve
  const offline = isOffline(dr?.recu_le)
  const ago = formatAgo(dr?.recu_le)
  const stalehum = humAgo(dr)

  return (
    <div
      className={`sonde-card${fullWidth ? ' sonde-full' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && onClick?.()}
    >
      {fullWidth ? (
        <>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <span className="sonde-name" style={{ marginBottom: 0 }}>{sonde.nom}</span>
            {offline && <span className="offline-badge"><Icon name="wifi-off" /> Hors ligne</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {dr ? (
              <>
                <span className="sonde-temp">{dr.temperature.toFixed(1)}°</span>
                {dr.humidite != null && (
                  <span className="sonde-hum">
                    <Icon name="droplet" style={{ color: '#1D9E75' }} />{dr.humidite}%
                    {stalehum && <span style={{ fontSize: 10, color: '#B5B0A8', marginLeft: 4 }}>{stalehum}</span>}
                  </span>
                )}
              </>
            ) : <span style={{ color: '#B5B0A8', fontSize: 14 }}>Aucune donnée</span>}
          </div>
          {ago && <div className="sonde-ago">{ago}</div>}
        </>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span className="sonde-name" style={{ marginBottom: 0 }}>{sonde.nom}</span>
            {offline && <Icon name="wifi-off" style={{ fontSize: 13, color: '#A32D2D' }} />}
          </div>
          {dr ? (
            <>
              <div className="sonde-temp">{dr.temperature.toFixed(1)}°</div>
              {dr.humidite != null && (
                <div className="sonde-hum">
                  <Icon name="droplet" style={{ color: '#1D9E75' }} />
                  {dr.humidite}%
                  {stalehum && <span style={{ fontSize: 10, color: '#B5B0A8', marginLeft: 4 }}>{stalehum}</span>}
                </div>
              )}
            </>
          ) : <div style={{ color: '#B5B0A8', fontSize: 14 }}>Aucune donnée</div>}
          {ago && <div className="sonde-ago">{ago}</div>}
        </>
      )}
    </div>
  )
}
