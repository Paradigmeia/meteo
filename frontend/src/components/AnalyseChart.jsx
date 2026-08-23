import { useRef, useState } from 'react'
import { niceTicks, linearScale, smooth } from '../utils/chartUtils'
import { getTimeTicks, histogramBins } from '../utils/analyseUtils'

const W = 900, H = 480
const PL = 56, PR = 56, PT = 24, PB = 32
const X0 = PL, X1 = W - PR, Y0 = PT, Y1 = H - PB

// Géométrie du mode "axes séparés" : un seul axe (gauche) par panneau, donc
// moins de marge droite nécessaire. PL reste identique au mode combiné pour
// garder les graduations temporelles alignées verticalement entre les deux
// panneaux et par rapport au mode combiné.
const SPLIT_X0 = PL, SPLIT_X1 = W - 20
const SPLIT_TOP_H = 220, SPLIT_TOP_Y0 = 16, SPLIT_TOP_Y1 = SPLIT_TOP_H - 8
const SPLIT_BOTTOM_H = 220, SPLIT_BOTTOM_Y0 = 8, SPLIT_BOTTOM_Y1 = SPLIT_BOTTOM_H - 32

function EmptyState({ message }) {
  return (
    <div style={{ height: H, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#B5B0A8', fontSize: 13 }}>
      {message}
    </div>
  )
}

function LineChart({ lines, bands, splitAxes, onHover }) {
  const [hoverX, setHoverX] = useState(null)
  const touchActiveRef = useRef(false)

  const allTimes = [
    ...lines.flatMap(l => l.points.map(p => p.t)),
    ...bands.flatMap(b => b.bands.flatMap(d => [d.dayStart, d.dayEnd])),
  ]
  if (allTimes.length === 0) {
    return <EmptyState message="Cochez au moins une donnée pour afficher le graphique" />
  }

  const minTime = Math.min(...allTimes)
  const maxTime = Math.max(...allTimes)
  const curX0 = splitAxes ? SPLIT_X0 : X0
  const curX1 = splitAxes ? SPLIT_X1 : X1
  const xOf = t => (maxTime === minTime ? (curX0 + curX1) / 2 : linearScale(t, minTime, maxTime, curX0, curX1))
  const invXOf = svgX => minTime + ((svgX - curX0) / (curX1 - curX0)) * (maxTime - minTime)

  const tempLines = lines.filter(l => l.axis === 'temp')
  const humLines = lines.filter(l => l.axis === 'hum')

  const tempValues = [
    ...tempLines.flatMap(l => l.points.map(p => p.v)),
    ...bands.flatMap(b => b.bands.flatMap(d => [d.min, d.max])),
  ]
  const humValues = humLines.flatMap(l => l.points.map(p => p.v))

  function buildScale(values, rangeTop, rangeBottom, tickCount) {
    if (!values.length) return { yOf: null, ticks: [] }
    const min = Math.min(...values), max = Math.max(...values)
    const span = max - min || 1
    const domMin = min - span * 0.08, domMax = max + span * 0.08
    return { yOf: v => linearScale(v, domMin, domMax, rangeBottom, rangeTop), ticks: niceTicks(min, max, tickCount) }
  }

  // Échelles du mode combiné (double axe, un seul graphique) — inchangées par rapport à avant
  const combinedTemp = buildScale(tempValues, Y0, Y1, 5)
  const combinedHum = buildScale(humValues, Y0, Y1, 4)
  // Échelles dédiées au mode séparé (chaque panneau a sa propre plage de pixels)
  const splitTemp = buildScale(tempValues, SPLIT_TOP_Y0, SPLIT_TOP_Y1, 5)
  const splitHum = buildScale(humValues, SPLIT_BOTTOM_Y0, SPLIT_BOTTOM_Y1, 4)

  const xTicks = getTimeTicks(minTime, maxTime, xOf)

  function nearestPoint(points, t) {
    let best = null, bestDist = Infinity
    for (const p of points) {
      const d = Math.abs(p.t - t)
      if (d < bestDist) { bestDist = d; best = p }
    }
    return best
  }

  // Convertit la position du pointeur en abscisse dans le repère du viewBox.
  // Une règle de trois sur getBoundingClientRect() serait fausse : les <svg> ont
  // une largeur fluide mais une hauteur fixe en px, donc dès que la carte dépasse
  // W (900) le preserveAspectRatio par défaut ("xMidYMid meet") dessine le contenu
  // à l'échelle 1 et le centre horizontalement (issue #26). getScreenCTM() intègre
  // cette transformation. Renvoie null si elle est indisponible — svg non rendu, ou
  // environnement sans getScreenCTM/DOMPoint (jsdom) : mieux vaut ne pas déplacer le
  // curseur que le poser au mauvais endroit.
  function getSvgX(e) {
    const touch = e.touches ? e.touches[0] : null
    if (e.touches && !touch) return null
    const ctm = typeof DOMPoint === 'undefined' ? null : e.currentTarget.getScreenCTM?.()
    if (!ctm) return null
    const client = new DOMPoint(touch ? touch.clientX : e.clientX, touch ? touch.clientY : e.clientY)
    const x = client.matrixTransform(ctm.inverse()).x
    if (!Number.isFinite(x)) return null
    return Math.max(curX0, Math.min(curX1, x))
  }

  function updateHover(e) {
    const svgX = getSvgX(e)
    if (svgX === null) return
    const t = invXOf(svgX)
    setHoverX(svgX)
    const values = lines
      .map(line => {
        const pt = nearestPoint(line.points, t)
        return pt ? { id: line.id, label: line.label, color: line.color, axis: line.axis, value: pt.v } : null
      })
      .filter(Boolean)
    onHover?.({ t, values })
  }

  function handleMouseMove(e) { if (!touchActiveRef.current) updateHover(e) }
  function handleMouseLeave() {
    if (!touchActiveRef.current) { setHoverX(null); onHover?.(null) }
  }
  function handleTouchStart(e) { touchActiveRef.current = true; updateHover(e) }
  function handleTouchMove(e) { e.preventDefault(); updateHover(e) }

  // Handlers communs aux 3 <svg> possibles (combiné, ou haut+bas en mode séparé) :
  // survoler n'importe lequel met à jour le même curseur et le même panneau de survol.
  const eventHandlers = {
    onMouseMove: handleMouseMove,
    onMouseLeave: handleMouseLeave,
    onTouchStart: handleTouchStart,
    onTouchMove: handleTouchMove,
  }

  function renderLine(line, yOf) {
    if (!yOf || line.points.length === 0) return null
    if (line.points.length === 1) {
      const p = line.points[0]
      return <circle key={line.id} cx={xOf(p.t)} cy={yOf(p.v)} r="2.5" fill={line.color} />
    }
    const pts = line.points.map(p => [xOf(p.t), yOf(p.v)])
    return (
      <path
        key={line.id} d={smooth(pts)} fill="none" stroke={line.color}
        strokeWidth={line.width ?? 2} strokeOpacity={line.opacity ?? 1}
        strokeDasharray={line.dash} strokeLinejoin="round"
      />
    )
  }

  if (!splitAxes) {
    return (
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H, touchAction: 'none', display: 'block' }} {...eventHandlers}>
        {combinedTemp.yOf && combinedTemp.ticks.map(v => (
          <line key={`grid-${v}`} x1={X0} y1={combinedTemp.yOf(v)} x2={X1} y2={combinedTemp.yOf(v)} stroke="rgba(0,0,0,0.06)" strokeWidth="0.5" />
        ))}
        {xTicks.map(t => (
          <line key={`vgrid-${t.time}`} x1={t.x} y1={Y0} x2={t.x} y2={Y1} stroke="rgba(0,0,0,0.04)" strokeWidth="0.5" strokeDasharray="2 4" />
        ))}
        {bands.flatMap(b => b.bands.map(d => (
          combinedTemp.yOf && (
            <rect
              key={`${b.id}-${d.dayStart}`}
              x={xOf(d.dayStart)} width={Math.max(0, xOf(d.dayEnd) - xOf(d.dayStart))}
              y={combinedTemp.yOf(d.max)} height={Math.max(0, combinedTemp.yOf(d.min) - combinedTemp.yOf(d.max))}
              fill={b.color} fillOpacity="0.14"
            />
          )
        )))}
        {lines.map(line => renderLine(line, line.axis === 'temp' ? combinedTemp.yOf : combinedHum.yOf))}
        {combinedTemp.yOf && combinedTemp.ticks.map(v => (
          <text key={`tl-${v}`} x={X0 - 6} y={combinedTemp.yOf(v) + 3.5} fill="#BA7517" fontSize="10" textAnchor="end">{v.toFixed(1)}°</text>
        ))}
        {combinedHum.yOf && combinedHum.ticks.map(v => (
          <text key={`hl-${v}`} x={X1 + 6} y={combinedHum.yOf(v) + 3.5} fill="#1D9E75" fontSize="10" textAnchor="start">{Math.round(v)}%</text>
        ))}
        {xTicks.map(t => (
          <text key={`xl-${t.time}`} x={t.x} y={H - 8} fill="#B5B0A8" fontSize="10" textAnchor="middle">{t.label}</text>
        ))}
        {hoverX != null && (
          <line x1={hoverX} y1={Y0} x2={hoverX} y2={Y1} stroke="#1A1714" strokeOpacity="0.15" strokeWidth="1" style={{ pointerEvents: 'none' }} />
        )}
      </svg>
    )
  }

  function renderSplitPanel({ height, y0, y1, scale, panelLines, panelBands, tickColor, formatTick, emptyLabel, showXLabels }) {
    return (
      <svg viewBox={`0 0 ${W} ${height}`} style={{ width: '100%', height, touchAction: 'none', display: 'block' }} {...eventHandlers}>
        {scale.yOf ? (
          <>
            {scale.ticks.map(v => (
              <line key={`grid-${v}`} x1={SPLIT_X0} y1={scale.yOf(v)} x2={SPLIT_X1} y2={scale.yOf(v)} stroke="rgba(0,0,0,0.06)" strokeWidth="0.5" />
            ))}
            {xTicks.map(t => (
              <line key={`vgrid-${t.time}`} x1={t.x} y1={y0} x2={t.x} y2={y1} stroke="rgba(0,0,0,0.04)" strokeWidth="0.5" strokeDasharray="2 4" />
            ))}
            {panelBands.flatMap(b => b.bands.map(d => (
              <rect
                key={`${b.id}-${d.dayStart}`}
                x={xOf(d.dayStart)} width={Math.max(0, xOf(d.dayEnd) - xOf(d.dayStart))}
                y={scale.yOf(d.max)} height={Math.max(0, scale.yOf(d.min) - scale.yOf(d.max))}
                fill={b.color} fillOpacity="0.14"
              />
            )))}
            {panelLines.map(line => renderLine(line, scale.yOf))}
            {scale.ticks.map(v => (
              <text key={`tl-${v}`} x={SPLIT_X0 - 6} y={scale.yOf(v) + 3.5} fill={tickColor} fontSize="10" textAnchor="end">{formatTick(v)}</text>
            ))}
            {hoverX != null && (
              <line x1={hoverX} y1={y0} x2={hoverX} y2={y1} stroke="#1A1714" strokeOpacity="0.15" strokeWidth="1" style={{ pointerEvents: 'none' }} />
            )}
          </>
        ) : (
          <text x={W / 2} y={height / 2} fill="#B5B0A8" fontSize="13" textAnchor="middle">{emptyLabel}</text>
        )}
        {showXLabels && xTicks.map(t => (
          <text key={`xl-${t.time}`} x={t.x} y={height - 8} fill="#B5B0A8" fontSize="10" textAnchor="middle">{t.label}</text>
        ))}
      </svg>
    )
  }

  return (
    <div>
      {renderSplitPanel({
        height: SPLIT_TOP_H, y0: SPLIT_TOP_Y0, y1: SPLIT_TOP_Y1, scale: splitTemp,
        panelLines: tempLines, panelBands: bands, tickColor: '#BA7517', formatTick: v => `${v.toFixed(1)}°`,
        emptyLabel: 'Aucune courbe de température active', showXLabels: false,
      })}

      <div style={{ borderTop: '1px solid rgba(0,0,0,.06)', margin: '8px 0' }} />

      {renderSplitPanel({
        height: SPLIT_BOTTOM_H, y0: SPLIT_BOTTOM_Y0, y1: SPLIT_BOTTOM_Y1, scale: splitHum,
        panelLines: humLines, panelBands: [], tickColor: '#1D9E75', formatTick: v => `${Math.round(v)}%`,
        emptyLabel: "Aucune courbe d'humidité active", showXLabels: true,
      })}
    </div>
  )
}

function DistributionChart({ data }) {
  const allValues = data.flatMap(d => d.values)
  if (allValues.length === 0) {
    return <EmptyState message="Cochez au moins une sonde pour afficher la distribution" />
  }
  const binSize = 0.5
  const globalMin = Math.floor(Math.min(...allValues) / binSize) * binSize
  const globalMax = Math.ceil(Math.max(...allValues) / binSize) * binSize
  const series = data.map(d => ({ ...d, bins: histogramBins(d.values, binSize, [globalMin, globalMax]) }))
  const numBins = series[0]?.bins.length || 1
  const maxCount = Math.max(1, ...series.flatMap(s => s.bins.map(b => b.count)))

  const xOf = v => linearScale(v, globalMin, globalMax, X0, X1)
  const yOf = c => linearScale(c, 0, maxCount, Y1, Y0)
  const barWidth = ((X1 - X0) / numBins) * 0.9
  const tempTicks = niceTicks(globalMin, globalMax, 6)
  const countTicks = niceTicks(0, maxCount, 4)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H, display: 'block' }}>
      {countTicks.map(c => (
        <line key={`grid-${c}`} x1={X0} y1={yOf(c)} x2={X1} y2={yOf(c)} stroke="rgba(0,0,0,0.06)" strokeWidth="0.5" />
      ))}
      {series.map(s => s.bins.filter(b => b.count > 0).map(b => (
        <rect
          key={`${s.id}-${b.from}`}
          x={xOf(b.from) + 1} width={Math.max(0, barWidth)}
          y={yOf(b.count)} height={Math.max(0, Y1 - yOf(b.count))}
          fill={s.color} fillOpacity="0.45" stroke={s.color} strokeWidth="1"
        />
      )))}
      {tempTicks.map(v => (
        <text key={`xl-${v}`} x={xOf(v)} y={H - 8} fill="#B5B0A8" fontSize="10" textAnchor="middle">{v.toFixed(1)}°</text>
      ))}
      {countTicks.map(c => (
        <text key={`yl-${c}`} x={X0 - 6} y={yOf(c) + 3.5} fill="#6B6560" fontSize="10" textAnchor="end">{Math.round(c)}</text>
      ))}
    </svg>
  )
}

function ScatterChart({ data }) {
  const allPoints = data.flatMap(d => d.points)
  if (allPoints.length === 0) {
    return <EmptyState message="Cochez au moins une sonde pour afficher le nuage de points" />
  }
  const temps = allPoints.map(p => p.temp)
  const hums = allPoints.map(p => p.hum)
  const minT = Math.min(...temps), maxT = Math.max(...temps)
  const minH = Math.min(...hums), maxH = Math.max(...hums)
  const spanT = (maxT - minT) || 1, spanH = (maxH - minH) || 1
  const xOf = v => linearScale(v, minT - spanT * 0.08, maxT + spanT * 0.08, X0, X1)
  const yOf = v => linearScale(v, minH - spanH * 0.08, maxH + spanH * 0.08, Y1, Y0)
  const tempTicks = niceTicks(minT, maxT, 6)
  const humTicks = niceTicks(minH, maxH, 5)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H, display: 'block' }}>
      {humTicks.map(v => (
        <line key={`grid-${v}`} x1={X0} y1={yOf(v)} x2={X1} y2={yOf(v)} stroke="rgba(0,0,0,0.06)" strokeWidth="0.5" />
      ))}
      {data.map(s => s.points.map((p, i) => (
        <circle key={`${s.id}-${i}`} cx={xOf(p.temp)} cy={yOf(p.hum)} r="3" fill={s.color} fillOpacity="0.55" />
      )))}
      {tempTicks.map(v => (
        <text key={`xl-${v}`} x={xOf(v)} y={H - 8} fill="#BA7517" fontSize="10" textAnchor="middle">{v.toFixed(1)}°</text>
      ))}
      {humTicks.map(v => (
        <text key={`yl-${v}`} x={X0 - 6} y={yOf(v) + 3.5} fill="#1D9E75" fontSize="10" textAnchor="end">{Math.round(v)}%</text>
      ))}
    </svg>
  )
}

export default function AnalyseChart({ mode, lines = [], bands = [], distributionData = [], scatterData = [], splitAxes = false, onHover }) {
  if (mode === 'distribution') return <DistributionChart data={distributionData} />
  if (mode === 'scatter') return <ScatterChart data={scatterData} />
  return <LineChart lines={lines} bands={bands} splitAxes={splitAxes} onHover={onHover} />
}
