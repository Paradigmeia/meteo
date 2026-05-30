import { formatAgo, isOffline } from '../meteoUtils'

export default function SondeCard({ sonde, fullWidth, onClick }) {
  const dr = sonde.dernier_releve
  const offline = isOffline(dr?.recu_le)
  const ago = formatAgo(dr?.recu_le)

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
            {offline && <span className="offline-badge"><i className="ti ti-wifi-off" /> Hors ligne</span>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {dr ? (
              <>
                <span className="sonde-temp">{dr.temperature.toFixed(1)}°</span>
                <span className="sonde-hum"><i className="ti ti-droplet" style={{ color: '#1D9E75' }} />{dr.humidite}%</span>
              </>
            ) : <span style={{ color: '#B5B0A8', fontSize: 14 }}>Aucune donnée</span>}
          </div>
          {ago && <div className="sonde-ago">{ago}</div>}
        </>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span className="sonde-name" style={{ marginBottom: 0 }}>{sonde.nom}</span>
            {offline && <i className="ti ti-wifi-off" style={{ fontSize: 13, color: '#A32D2D' }} />}
          </div>
          {dr ? (
            <>
              <div className="sonde-temp">{dr.temperature.toFixed(1)}°</div>
              <div className="sonde-hum">
                <i className="ti ti-droplet" style={{ color: '#1D9E75' }} />
                {dr.humidite}%
              </div>
            </>
          ) : <div style={{ color: '#B5B0A8', fontSize: 14 }}>Aucune donnée</div>}
          {ago && <div className="sonde-ago">{ago}</div>}
        </>
      )}
    </div>
  )
}
