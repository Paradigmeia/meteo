import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import AnalyseChart from './AnalyseChart'
import { useAnalyseReleves } from '../hooks/useAnalyseReleves'
import {
  PERIOD_OPTIONS, sondeColor, METEO_COLOR,
  AVG_1H_DASH, AVG_6H_DASH,
  movingAverage, dailyMinMaxBand,
  loadAnalysePrefs, saveAnalysePrefs, rangeBoundsMs,
} from '../utils/analyseUtils'

// Dimensions fluides du graphique : le viewBox SVG reprend les dimensions
// mesurées de la carte, qui s'étire jusqu'au bas de la fenêtre.
// MIN_CHART_HEIGHT est la hauteur historique, conservée comme plancher pour ne
// pas écraser le graphique sur petite fenêtre ou résolution basse ;
// MIN_CHART_WIDTH évite que les graduations se chevauchent sur carte étroite
// (en deçà, le SVG se remet à l'échelle et le graphique est simplement réduit).
const CHART_BOTTOM_MARGIN = 32
const MIN_CHART_HEIGHT = 480
const MIN_CHART_WIDTH = 600

function toIso(datetimeLocal) {
  if (!datetimeLocal) return null
  const d = new Date(datetimeLocal)
  return Number.isNaN(d.getTime()) ? null : d.toISOString()
}

function formatHoverTime(t) {
  return new Date(t).toLocaleString('fr', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export default function AnalyseView({ sondes, meteo, onBack }) {
  const initialPrefs = useMemo(() => loadAnalysePrefs() ?? {}, [])

  const [checkedSondes, setCheckedSondes] = useState(() => new Set(initialPrefs.checkedSondes ?? []))
  const [meteoChecked, setMeteoChecked] = useState(() => initialPrefs.meteoChecked ?? false)
  const [avg1h, setAvg1h] = useState(() => initialPrefs.avg1h ?? false)
  const [avg6h, setAvg6h] = useState(() => initialPrefs.avg6h ?? false)
  const [minMaxBand, setMinMaxBand] = useState(() => initialPrefs.minMaxBand ?? false)
  const [mode, setMode] = useState(() => initialPrefs.mode ?? 'line')
  const [quickCode, setQuickCode] = useState(() => initialPrefs.quickCode ?? '24h')
  const [splitAxes, setSplitAxes] = useState(() => initialPrefs.splitAxes ?? false)
  const [showTemp, setShowTemp] = useState(() => initialPrefs.showTemp ?? true)
  const [showHum, setShowHum] = useState(() => initialPrefs.showHum ?? true)

  const [useCustomRange, setUseCustomRange] = useState(false)
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [hoverInfo, setHoverInfo] = useState(null)

  const mainRef = useRef(null)
  const chartCardRef = useRef(null)
  const [chartSize, setChartSize] = useState({ width: MIN_CHART_WIDTH, height: MIN_CHART_HEIGHT })

  useEffect(() => {
    saveAnalysePrefs({
      checkedSondes: [...checkedSondes],
      meteoChecked, avg1h, avg6h, minMaxBand,
      mode, quickCode, splitAxes, showTemp, showHum,
    })
  }, [checkedSondes, meteoChecked, avg1h, avg6h, minMaxBand, mode, quickCode, splitAxes, showTemp, showHum])

  const slugs = useMemo(() => sondes.map(s => s.slug), [sondes])
  const customRange = useCustomRange && customFrom && customTo
    ? { from: toIso(customFrom), to: toIso(customTo) }
    : null
  const { data: relevesBySlug } = useAnalyseReleves(slugs, quickCode, customRange)
  const { start: rangeStart, end: rangeEnd } = rangeBoundsMs(quickCode, customRange)

  function selectQuick(code) {
    setQuickCode(code)
    setUseCustomRange(false)
    setCustomFrom('')
    setCustomTo('')
  }

  function handleFromChange(v) {
    setCustomFrom(v)
    if (v && customTo) setUseCustomRange(true)
  }

  function handleToChange(v) {
    setCustomTo(v)
    if (customFrom && v) setUseCustomRange(true)
  }

  // Le panneau de survol garde la dernière valeur survolée : on le vide en même
  // temps que le filtre change, sinon il continuerait d'afficher des séries
  // désormais masquées jusqu'au prochain survol.
  function toggleMeasureType(setter, checked) {
    setter(checked)
    setHoverInfo(null)
  }

  function toggleSonde(slug) {
    setCheckedSondes(prev => {
      const next = new Set(prev)
      if (next.has(slug)) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  const checkedList = sondes.filter(s => checkedSondes.has(s.slug))

  const rawLines = checkedList.flatMap(s => {
    const releves = relevesBySlug[s.slug] ?? []
    const color = sondeColor(s.slug)
    const tempPts = releves.filter(r => r.temperature != null).map(r => ({ t: new Date(r.recu_le).getTime(), v: r.temperature }))
    const humPts = releves.filter(r => r.humidite != null).map(r => ({ t: new Date(r.recu_le).getTime(), v: r.humidite }))
    const out = []
    if (tempPts.length) out.push({ id: `${s.slug}-temp`, label: `${s.nom} — Température`, color, axis: 'temp', width: 2, points: tempPts })
    if (humPts.length) out.push({ id: `${s.slug}-hum`, label: `${s.nom} — Humidité`, color, axis: 'hum', width: 2, dash: splitAxes ? undefined : '4 2', points: humPts })
    return out
  })

  const avgLines = checkedList.flatMap(s => {
    const releves = relevesBySlug[s.slug] ?? []
    const color = sondeColor(s.slug)
    const out = []
    if (avg1h) {
      const pts = movingAverage(releves, 3_600_000).map(r => ({ t: new Date(r.recu_le).getTime(), v: r.temperature }))
      if (pts.length) out.push({ id: `${s.slug}-avg1h`, label: `${s.nom} — Moy. glissante 1h`, color, axis: 'temp', width: 1.5, opacity: 0.8, dash: AVG_1H_DASH, points: pts })
    }
    if (avg6h) {
      const pts = movingAverage(releves, 6 * 3_600_000).map(r => ({ t: new Date(r.recu_le).getTime(), v: r.temperature }))
      if (pts.length) out.push({ id: `${s.slug}-avg6h`, label: `${s.nom} — Moy. glissante 6h`, color, axis: 'temp', width: 2, opacity: 0.55, dash: AVG_6H_DASH, points: pts })
    }
    return out
  })

  const bandEntries = minMaxBand
    ? checkedList
      .map(s => ({
        id: `${s.slug}-band`, label: `${s.nom} — Bande min/max journalière`, color: sondeColor(s.slug),
        bands: dailyMinMaxBand(relevesBySlug[s.slug] ?? []),
      }))
      .filter(b => b.bands.length)
    : []

  const meteoLines = []
  if (meteoChecked && meteo?.hourly?.time) {
    const pts = meteo.hourly.time
      .map((t, i) => ({ t: new Date(t).getTime(), v: meteo.hourly.temperature_2m[i] }))
      .filter(p => p.t >= rangeStart && p.t <= rangeEnd)
    if (pts.length) meteoLines.push({ id: 'meteo', label: 'Open-Meteo Ascain', color: METEO_COLOR, axis: 'temp', width: 1.5, dash: '2 2', points: pts })
  }

  const lines = [...rawLines, ...avgLines, ...meteoLines]

  // Filtre par type de mesure : masque toutes les courbes de l'axe décoché,
  // toutes catégories confondues (brutes, moyennes glissantes, indices de
  // confort, ΔT, Open-Meteo). La bande min/max est intrinsèquement une donnée
  // de température, elle suit donc showTemp.
  const visibleLines = lines.filter(l => (l.axis === 'temp' ? showTemp : showHum))
  const visibleBands = showTemp ? bandEntries : []

  const distributionData = checkedList.map(s => ({
    id: s.slug, label: s.nom, color: sondeColor(s.slug),
    values: (relevesBySlug[s.slug] ?? []).filter(r => r.temperature != null).map(r => r.temperature),
  }))

  const scatterData = checkedList.map(s => ({
    id: s.slug, label: s.nom, color: sondeColor(s.slug),
    points: (relevesBySlug[s.slug] ?? [])
      .filter(r => r.temperature != null && r.humidite != null)
      .map(r => ({ temp: r.temperature, hum: r.humidite })),
  }))

  const legendItems = mode === 'distribution'
    ? distributionData.filter(d => d.values.length).map(d => ({ id: d.id, color: d.color, label: d.label }))
    : mode === 'scatter'
      ? scatterData.filter(d => d.points.length).map(d => ({ id: d.id, color: d.color, label: d.label }))
      : [...visibleLines, ...visibleBands]

  // Mesure la zone de dessin utile de la carte graphique : sa largeur intérieure,
  // et l'espace vertical restant jusqu'au bas de la fenêtre. On raisonne en
  // coordonnées document (rect.top + scrollY) pour que la mesure ne dépende pas
  // du défilement ; changer la taille du graphique ne déplace pas le haut de la
  // carte ni sa largeur, donc pas de boucle de rétroaction.
  useLayoutEffect(() => {
    function measure() {
      const card = chartCardRef.current
      const main = mainRef.current
      if (!card || !main) return
      const styles = window.getComputedStyle(card)
      const px = prop => parseFloat(styles[prop]) || 0
      const vInsets = px('paddingTop') + px('paddingBottom') + px('borderTopWidth') + px('borderBottomWidth')
      const cardRect = card.getBoundingClientRect()
      // Ce qui suit la carte dans la colonne principale (légende, marge basse)
      // doit rester visible : on le déduit de la hauteur disponible. `.analyse-main`
      // est un élément de grille, donc racine de contexte de formatage : la marge
      // basse de la carte est bien comprise dans la hauteur de la colonne.
      const trailing = Math.max(0, main.getBoundingClientRect().bottom - cardRect.bottom)
      const available = window.innerHeight - (cardRect.top + window.scrollY)
        - trailing - CHART_BOTTOM_MARGIN - vInsets
      // clientWidth exclut les bordures mais pas les paddings.
      const width = Math.max(MIN_CHART_WIDTH, Math.round(card.clientWidth - px('paddingLeft') - px('paddingRight')))
      const height = Math.max(MIN_CHART_HEIGHT, Math.round(available))
      setChartSize(prev => (prev.width === width && prev.height === height ? prev : { width, height }))
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
    // `mode` fait apparaître/disparaître le panneau de survol et la bascule
    // d'axes au-dessus de la carte ; la taille de la légende change ce qui suit.
  }, [mode, legendItems.length])

  return (
    <div className="analyse-container">
      <button className="back-btn" onClick={onBack}>
        <i className="ti ti-arrow-left" />
        Retour
      </button>

      <div className="header-title" style={{ marginBottom: '1.5rem' }}>Vue Analyse</div>

      <div className="analyse-layout">
        <aside className="analyse-sidebar">
          <div className="analyse-group">
            <p className="section-label">Mesures brutes par sonde</p>
            {sondes.map(s => (
              <label key={s.slug} className="analyse-check">
                <input type="checkbox" checked={checkedSondes.has(s.slug)} onChange={() => toggleSonde(s.slug)} />
                <span className="analyse-swatch" style={{ background: sondeColor(s.slug) }} />
                {s.nom}
              </label>
            ))}
          </div>

          <div className="analyse-group">
            <p className="section-label">Comparaison</p>
            <label className="analyse-check">
              <input type="checkbox" checked={meteoChecked} onChange={e => setMeteoChecked(e.target.checked)} />
              Température Open-Meteo Ascain
            </label>
          </div>

          <div className="analyse-group">
            <p className="section-label">Moyennes glissantes</p>
            <label className="analyse-check">
              <input type="checkbox" checked={avg1h} onChange={e => setAvg1h(e.target.checked)} />
              1 heure
            </label>
            <label className="analyse-check">
              <input type="checkbox" checked={avg6h} onChange={e => setAvg6h(e.target.checked)} />
              6 heures
            </label>
          </div>

          <div className="analyse-group">
            <p className="section-label">Bande min/max</p>
            <label className="analyse-check">
              <input type="checkbox" checked={minMaxBand} onChange={e => setMinMaxBand(e.target.checked)} />
              Bande min/max journalière
            </label>
          </div>

          <div className="analyse-group">
            <p className="section-label">Mode d'affichage</p>
            <label className="analyse-check">
              <input
                type="checkbox" checked={mode === 'distribution'}
                onChange={e => setMode(e.target.checked ? 'distribution' : 'line')}
              />
              Histogramme de distribution
            </label>
            <label className="analyse-check">
              <input
                type="checkbox" checked={mode === 'scatter'}
                onChange={e => setMode(e.target.checked ? 'scatter' : 'line')}
              />
              Nuage de points (temp/humidité)
            </label>
          </div>

          {/* Placée en dernier : le filtre n'existe qu'en mode ligne, et le voir
              disparaître ne doit pas décaler les cases situées au-dessus — la
              case "Histogramme" qu'on vient de cocher resterait sinon sous le
              curseur alors qu'une autre a pris sa place. */}
          {mode === 'line' && (
            <div className="analyse-group">
              <p className="section-label">Type de mesure</p>
              <label className="analyse-check">
                <input type="checkbox" checked={showTemp} onChange={e => toggleMeasureType(setShowTemp, e.target.checked)} />
                Température
              </label>
              <label className="analyse-check">
                <input type="checkbox" checked={showHum} onChange={e => toggleMeasureType(setShowHum, e.target.checked)} />
                Humidité
              </label>
            </div>
          )}
        </aside>

        <div className="analyse-main" ref={mainRef}>
          <div className="analyse-range">
            <div className="periods">
              {PERIOD_OPTIONS.map(p => (
                <button
                  key={p.code}
                  className={`period-btn${!useCustomRange && quickCode === p.code ? ' active' : ''}`}
                  onClick={() => selectQuick(p.code)}
                >
                  {p.label}
                </button>
              ))}
            </div>
            <div className="analyse-date-pickers">
              <label className="analyse-date-field">
                Du
                <input type="datetime-local" value={customFrom} onChange={e => handleFromChange(e.target.value)} />
              </label>
              <label className="analyse-date-field">
                Au
                <input type="datetime-local" value={customTo} onChange={e => handleToChange(e.target.value)} />
              </label>
            </div>
          </div>

          {mode === 'line' && (
            <div className="hover-panel">
              {hoverInfo ? (
                <>
                  <div className="hover-panel-time">{formatHoverTime(hoverInfo.t)}</div>
                  <div className="hover-panel-values" style={{ flexWrap: 'wrap' }}>
                    {hoverInfo.values.map(v => (
                      <span key={v.id} style={{ color: v.color, fontSize: 13 }}>
                        {v.label} : {v.value.toFixed(1)}{v.axis === 'temp' ? '°C' : '%'}
                      </span>
                    ))}
                    {hoverInfo.values.length === 0 && <span style={{ color: '#B5B0A8', fontSize: 13 }}>Aucune courbe active</span>}
                  </div>
                </>
              ) : (
                <div className="hover-panel-time">Survolez le graphique pour voir le détail</div>
              )}
            </div>
          )}

          {mode === 'line' && (
            <div className="axis-toggle" role="group" aria-label="Affichage des axes">
              <button type="button" aria-pressed={!splitAxes} className={`axis-toggle-btn${!splitAxes ? ' active' : ''}`} onClick={() => setSplitAxes(false)}>
                Combiné
              </button>
              <button type="button" aria-pressed={splitAxes} className={`axis-toggle-btn${splitAxes ? ' active' : ''}`} onClick={() => setSplitAxes(true)}>
                Séparé
              </button>
            </div>
          )}

          <div className="chart-card" ref={chartCardRef}>
            <AnalyseChart
              mode={mode}
              lines={visibleLines}
              bands={visibleBands}
              distributionData={distributionData}
              scatterData={scatterData}
              splitAxes={splitAxes}
              showTemp={showTemp}
              showHum={showHum}
              width={chartSize.width}
              height={chartSize.height}
              onHover={setHoverInfo}
            />
          </div>

          {legendItems.length > 0 && (
            <div className="chart-legend analyse-legend">
              {legendItems.map(item => (
                <span key={item.id} className="legend-item">
                  <span className="analyse-swatch" style={{ background: item.color }} />
                  {item.label}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
