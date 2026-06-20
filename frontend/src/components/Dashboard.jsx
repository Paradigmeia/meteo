import MeteoCard from './MeteoCard'
import SondeCard from './SondeCard'
import { useIsDesktop } from '../hooks/useIsDesktop'

export default function Dashboard({ sondes, meteo, onSelectSonde, onOpenAnalyse }) {
  const isDesktop = useIsDesktop()
  const now = new Date()
  const dateLabel = now.toLocaleDateString('fr', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' })
  const dateFormatted = dateLabel.charAt(0).toUpperCase() + dateLabel.slice(1)

  const interior = sondes.filter(s => !s.slug.startsWith('ext'))
  const exterior = sondes.filter(s => s.slug.startsWith('ext'))

  // Fallback: si pas de convention de slug, utiliser l'ordre
  const intSondes = interior.length > 0 ? interior : sondes.slice(0, Math.max(sondes.length - 1, 0))
  const extSondes = exterior.length > 0 ? exterior : sondes.slice(-1)

  return (
    <>
      <div className="header">
        <div>
          <div className="header-sub">{dateFormatted}</div>
          <div className="header-title">La maison</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          {isDesktop && (
            <button className="analyse-btn" onClick={onOpenAnalyse} aria-label="Vue Analyse">
              <i className="ti ti-chart-dots-3" style={{ fontSize: 22, color: '#B5B0A8' }} />
            </button>
          )}
          <i className="ti ti-home-2" style={{ fontSize: 24, color: '#B5B0A8' }} />
        </div>
      </div>

      <MeteoCard meteo={meteo} />

      {intSondes.length > 0 && (
        <>
          <p className="section-label">Intérieur</p>
          <div className="sonde-grid">
            {intSondes.map(s => (
              <SondeCard key={s.slug} sonde={s} fullWidth={intSondes.length === 1} onClick={() => onSelectSonde(s.slug)} />
            ))}
          </div>
        </>
      )}

      {extSondes.length > 0 && (
        <>
          <p className="section-label">Extérieur</p>
          <div className="sonde-grid">
            {extSondes.map(s => (
              <SondeCard key={s.slug} sonde={s} fullWidth={extSondes.length === 1} onClick={() => onSelectSonde(s.slug)} />
            ))}
          </div>
        </>
      )}

      {sondes.length === 0 && (
        <p style={{ color: '#8C8880', fontSize: 14, textAlign: 'center', marginTop: 32 }}>
          Chargement des sondes…
        </p>
      )}
    </>
  )
}
