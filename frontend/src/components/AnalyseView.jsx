import { useEffect, useMemo, useState } from 'react'
import AnalyseChart from './AnalyseChart'
import { useAnalyseReleves } from '../hooks/useAnalyseReleves'
import {
  PERIOD_OPTIONS, sondeColor, METEO_COLOR, DELTA_T_COLOR,
  AVG_1H_DASH, AVG_6H_DASH, HEAT_INDEX_DASH, DEW_POINT_DASH,
  movingAverage, dailyMinMaxBand, heatIndexC, dewPointC, computeDeltaT,
  loadAnalysePrefs, saveAnalysePrefs, rangeBoundsMs,
} from '../utils/analyseUtils'

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
  const [heatIndex, setHeatIndex] = useState(() => initialPrefs.heatIndex ?? false)
  const [dewPoint, setDewPoint] = useState(() => initialPrefs.dewPoint ?? false)
  const [deltaT, setDeltaT] = useState(() => initialPrefs.deltaT ?? false)
  const [mode, setMode] = useState(() => initialPrefs.mode ?? 'line')
  const [quickCode, setQuickCode] = useState(() => initialPrefs.quickCode ?? '24h')
  const [splitAxes, setSplitAxes] = useState(() => initialPrefs.splitAxes ?? false)

  const [useCustomRange, setUseCustomRange] = useState(false)
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [hoverInfo, setHoverInfo] = useState(null)

  useEffect(() => {
    saveAnalysePrefs({
      checkedSondes: [...checkedSondes],
      meteoChecked, avg1h, avg6h, minMaxBand, heatIndex, dewPoint, deltaT,
      mode, quickCode, splitAxes,
    })
  }, [checkedSondes, meteoChecked, avg1h, avg6h, minMaxBand, heatIndex, dewPoint, deltaT, mode, quickCode, splitAxes])

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

  const comfortLines = checkedList.flatMap(s => {
    const releves = relevesBySlug[s.slug] ?? []
    const color = sondeColor(s.slug)
    const out = []
    if (heatIndex) {
      const pts = releves
        .map(r => ({ t: new Date(r.recu_le).getTime(), v: heatIndexC(r.temperature, r.humidite) }))
        .filter(p => p.v != null)
      if (pts.length) out.push({ id: `${s.slug}-hi`, label: `${s.nom} — Indice de chaleur`, color, axis: 'temp', width: 1.5, dash: HEAT_INDEX_DASH, points: pts })
    }
    if (dewPoint) {
      const pts = releves
        .map(r => ({ t: new Date(r.recu_le).getTime(), v: dewPointC(r.temperature, r.humidite) }))
        .filter(p => p.v != null)
      if (pts.length) out.push({ id: `${s.slug}-td`, label: `${s.nom} — Point de rosée`, color, axis: 'temp', width: 1.5, dash: DEW_POINT_DASH, points: pts })
    }
    return out
  })

  const interiorSlugs = sondes.filter(s => !s.slug.startsWith('ext')).map(s => s.slug)
  const exteriorSlugs = sondes.filter(s => s.slug.startsWith('ext')).map(s => s.slug)
  const deltaTLines = []
  if (deltaT && interiorSlugs.length && exteriorSlugs.length) {
    const interiorReleves = interiorSlugs.flatMap(slug => relevesBySlug[slug] ?? [])
    const exteriorReleves = exteriorSlugs.flatMap(slug => relevesBySlug[slug] ?? [])
    const pts = computeDeltaT(interiorReleves, exteriorReleves).map(d => ({ t: new Date(d.recu_le).getTime(), v: d.delta }))
    if (pts.length) deltaTLines.push({ id: 'deltaT', label: 'Écart intérieur/extérieur (ΔT)', color: DELTA_T_COLOR, axis: 'temp', width: 1.5, dash: '5 2', points: pts })
  }

  const meteoLines = []
  if (meteoChecked && meteo?.hourly?.time) {
    const pts = meteo.hourly.time
      .map((t, i) => ({ t: new Date(t).getTime(), v: meteo.hourly.temperature_2m[i] }))
      .filter(p => p.t >= rangeStart && p.t <= rangeEnd)
    if (pts.length) meteoLines.push({ id: 'meteo', label: 'Open-Meteo Ascain', color: METEO_COLOR, axis: 'temp', width: 1.5, dash: '2 2', points: pts })
  }

  const lines = [...rawLines, ...avgLines, ...comfortLines, ...deltaTLines, ...meteoLines]

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
      : [...lines, ...bandEntries]

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
            <p className="section-label">Indices de confort</p>
            <label className="analyse-check">
              <input type="checkbox" checked={heatIndex} onChange={e => setHeatIndex(e.target.checked)} />
              Chaleur ressentie (Heat Index)
            </label>
            <label className="analyse-check">
              <input type="checkbox" checked={dewPoint} onChange={e => setDewPoint(e.target.checked)} />
              Point de rosée
            </label>
            <label className="analyse-check">
              <input type="checkbox" checked={deltaT} onChange={e => setDeltaT(e.target.checked)} />
              Écart intérieur/extérieur (ΔT)
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
        </aside>

        <div className="analyse-main">
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

          <div className="chart-card">
            <AnalyseChart
              mode={mode}
              lines={lines}
              bands={bandEntries}
              distributionData={distributionData}
              scatterData={scatterData}
              splitAxes={splitAxes}
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
