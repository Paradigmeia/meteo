import { formatAgo, isOffline } from '../meteoUtils'
import Icon from './Icon'

// Une grandeur en retard sur le dernier signe de vie de la sonde. Les deux
// arrivent en relevés séparés — le Shelly les envoie en deux actions distinctes
// — et l'une peut cesser de remonter pendant que l'autre continue : c'est alors
// la valeur affichée qui est périmée, pas la sonde. Le marqueur ne dit donc rien
// pour la plus récente des deux, dont l'écart est nul par construction.
function retardAgo(dr, isoGrandeur) {
  if (!isoGrandeur || !dr?.recu_le) return null
  const diffMs = new Date(dr.recu_le).getTime() - new Date(isoGrandeur).getTime()
  if (diffMs < 30 * 60 * 1000) return null
  return formatAgo(isoGrandeur)
}

export default function SondeCard({ sonde, fullWidth, onClick }) {
  const dr = sonde.dernier_releve
  const offline = isOffline(dr?.recu_le)
  const ago = formatAgo(dr?.recu_le)
  // La température doit être marquée comme l'humidité : depuis #43, `recu_le`
  // suit la plus récente des deux, donc une sonde dont seule l'humidité remonte
  // n'est plus « hors ligne » — et sans ce marqueur, sa température figée
  // s'afficherait sans rien signaler du tout.
  // `dernier_releve` existe dès qu'UNE des deux grandeurs est présente : une
  // sonde qui n'aurait jamais envoyé de température renvoie `temperature: null`,
  // et `toFixed` sur null ferait disparaître tout le dashboard, faute d'error
  // boundary. Le marqueur, lui, reste porté par l'horodatage : une valeur
  // absente n'a pas d'âge à afficher.
  const staletemp = retardAgo(dr, dr?.recu_le_temp)
  const stalehum = retardAgo(dr, dr?.recu_le_hum)

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
                <span className="sonde-temp">
                  {dr.temperature != null ? `${dr.temperature.toFixed(1)}°` : '—'}
                  {staletemp && <span className="mesure-retard">{staletemp}</span>}
                </span>
                {dr.humidite != null && (
                  <span className="sonde-hum">
                    <Icon name="droplet" style={{ color: '#1D9E75' }} />{dr.humidite}%
                    {stalehum && <span className="mesure-retard">{stalehum}</span>}
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
            {offline && <Icon name="wifi-off" label="Hors ligne" style={{ fontSize: 13, color: '#A32D2D' }} />}
          </div>
          {dr ? (
            <>
              <div className="sonde-temp">
                {dr.temperature != null ? `${dr.temperature.toFixed(1)}°` : '—'}
                {staletemp && <span className="mesure-retard">{staletemp}</span>}
              </div>
              {dr.humidite != null && (
                <div className="sonde-hum">
                  <Icon name="droplet" style={{ color: '#1D9E75' }} />
                  {dr.humidite}%
                  {stalehum && <span className="mesure-retard">{stalehum}</span>}
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
