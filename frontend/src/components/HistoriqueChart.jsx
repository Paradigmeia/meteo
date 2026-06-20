import { useState, useRef } from 'react'
import { niceTicks, linearScale, smooth, getXTicks } from '../utils/chartUtils'

const W = 360, H = 200
const PL = 36, PR = 36, PT = 20, PB = 20
const X0 = PL, X1 = W - PR, Y0 = PT, Y1 = H - PB

function clampX(x) { return Math.max(X0 + 2, Math.min(X1 - 2, x)) }

export default function HistoriqueChart({ releves, period, onHover }) {
  const [tooltip, setTooltip] = useState(null)
  const touchActiveRef = useRef(false)

  if (!releves || releves.length < 2) {
    return (
      <div style={{ height: H, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#B5B0A8', fontSize: 13 }}>
        Pas assez de données
      </div>
    )
  }

  const times = releves.map(r => new Date(r.recu_le).getTime())
  const minTime = Math.min(...times)
  const maxTime = Math.max(...times)
  const xOf = t => maxTime === minTime
    ? (X0 + X1) / 2
    : linearScale(t, minTime, maxTime, X0, X1)

  // Temperature
  const tempReleves = releves.filter(r => r.temperature != null)
  let yOfT = null, tempPath = null, tempTicks = [], maxTempPt = null, minTempPt = null
  if (tempReleves.length >= 2) {
    const temps = tempReleves.map(r => r.temperature)
    const minT = Math.min(...temps), maxT = Math.max(...temps)
    const span = maxT - minT || 1
    const domMinT = minT - span * 0.08, domMaxT = maxT + span * 0.08
    yOfT = v => linearScale(v, domMinT, domMaxT, Y1, Y0)
    tempTicks = niceTicks(minT, maxT, 4)
    const pts = tempReleves.map(r => [xOf(new Date(r.recu_le).getTime()), yOfT(r.temperature)])
    tempPath = smooth(pts)
    const maxI = temps.indexOf(maxT), minI = temps.indexOf(minT)
    maxTempPt = { x: pts[maxI][0], y: pts[maxI][1], val: maxT }
    minTempPt = { x: pts[minI][0], y: pts[minI][1], val: minT }
  }

  // Humidity
  const humReleves = releves.filter(r => r.humidite != null)
  let yOfH = null, humPath = null, humTicks = [], maxHumPt = null, minHumPt = null
  if (humReleves.length >= 2) {
    const hums = humReleves.map(r => r.humidite)
    const minH = Math.min(...hums), maxH = Math.max(...hums)
    const span = maxH - minH || 1
    const domMinH = minH - span * 0.08, domMaxH = maxH + span * 0.08
    yOfH = v => linearScale(v, domMinH, domMaxH, Y1, Y0)
    humTicks = niceTicks(minH, maxH, 3)
    const pts = humReleves.map(r => [xOf(new Date(r.recu_le).getTime()), yOfH(r.humidite)])
    humPath = smooth(pts)
    const maxI = hums.indexOf(maxH), minI = hums.indexOf(minH)
    maxHumPt = { x: pts[maxI][0], y: pts[maxI][1], val: maxH }
    minHumPt = { x: pts[minI][0], y: pts[minI][1], val: minH }
  }

  const xTicks = getXTicks(releves, period, X0, X1)

  // Find the releve in a list whose x position is closest to an SVG x coordinate
  function findClosestIn(list, svgX) {
    let best = null, bestDist = Infinity
    for (const r of list) {
      const rx = xOf(new Date(r.recu_le).getTime())
      const d = Math.abs(rx - svgX)
      if (d < bestDist) { bestDist = d; best = r }
    }
    return best
  }

  function getSvgX(e) {
    const rect = e.currentTarget.getBoundingClientRect()
    const clientX = e.touches ? e.touches[0].clientX : e.clientX
    return ((clientX - rect.left) / rect.width) * W
  }

  function updateTooltip(e) {
    const svgX = getSvgX(e)
    const anchor = findClosestIn(releves, svgX)
    if (!anchor) return
    // Température et humidité sont cherchées indépendamment : un même relevé peut
    // ne contenir que l'une des deux valeurs (events Shelly séparés)
    const closestTemp = findClosestIn(tempReleves, svgX)
    const closestHum = findClosestIn(humReleves, svgX)
    setTooltip({ x: xOf(new Date(anchor.recu_le).getTime()) })
    onHover?.({
      recu_le: anchor.recu_le,
      temperature: closestTemp ? closestTemp.temperature : null,
      humidite: closestHum ? closestHum.humidite : null,
    })
  }

  function handleMouseMove(e) {
    if (touchActiveRef.current) return
    updateTooltip(e)
  }

  function handleMouseLeave() {
    if (!touchActiveRef.current) {
      setTooltip(null)
      onHover?.(null)
    }
  }

  function handleTouchStart(e) {
    touchActiveRef.current = true
    updateTooltip(e)
  }

  function handleTouchMove(e) {
    e.preventDefault()
    updateTooltip(e)
  }

  // Ligne de repérage verticale (le détail des valeurs est affiché par le panneau
  // de survol fixe dans Detail.jsx, via la prop onHover)
  const hoverLineEl = tooltip && (
    <line x1={tooltip.x} y1={Y0} x2={tooltip.x} y2={Y1} stroke="#1A1714" strokeOpacity="0.15" strokeWidth="1" style={{ pointerEvents: 'none' }} />
  )

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      style={{ width: '100%', height: H, touchAction: 'none', display: 'block' }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
    >
      {/* Horizontal grid (temp ticks only) */}
      {yOfT && tempTicks.map(v => (
        <line key={v} x1={X0} y1={yOfT(v)} x2={X1} y2={yOfT(v)}
          stroke="rgba(0,0,0,0.06)" strokeWidth="0.5" />
      ))}

      {/* Vertical grid (X ticks) */}
      {xTicks.map(t => (
        <line key={t.time} x1={t.x} y1={Y0} x2={t.x} y2={Y1}
          stroke="rgba(0,0,0,0.04)" strokeWidth="0.5" strokeDasharray="2 4" />
      ))}

      {/* Curves */}
      {tempPath && <path d={tempPath} fill="none" stroke="#BA7517" strokeWidth="2" strokeLinejoin="round" />}
      {humPath && <path d={humPath} fill="none" stroke="#1D9E75" strokeWidth="2" strokeLinejoin="round" strokeDasharray="4 2" />}

      {/* Y axis temp labels (left) */}
      {yOfT && tempTicks.map(v => (
        <text key={v} x={X0 - 4} y={yOfT(v) + 3.5} fill="#BA7517" fontSize="9" textAnchor="end">{v.toFixed(1)}°</text>
      ))}

      {/* Y axis hum labels (right) */}
      {yOfH && humTicks.map(v => (
        <text key={v} x={X1 + 4} y={yOfH(v) + 3.5} fill="#1D9E75" fontSize="9" textAnchor="start">{Math.round(v)}%</text>
      ))}

      {/* X axis labels */}
      {xTicks.map(t => (
        <text key={t.time} x={t.x} y={H - 5} fill="#B5B0A8" fontSize="9" textAnchor="middle">{t.label}</text>
      ))}

      {/* Min/max temp labels */}
      {maxTempPt && (
        <text
          x={clampX(maxTempPt.x)} y={Math.max(PT - 4, maxTempPt.y - 5)}
          fill="#BA7517" fontSize="10" textAnchor="middle">▲ {maxTempPt.val.toFixed(1)}°</text>
      )}
      {minTempPt && (
        <text
          x={clampX(minTempPt.x)} y={Math.min(Y1 + 14, minTempPt.y + 13)}
          fill="#BA7517" fontSize="10" textAnchor="middle">▼ {minTempPt.val.toFixed(1)}°</text>
      )}

      {/* Min/max hum labels */}
      {maxHumPt && (
        <text
          x={clampX(maxHumPt.x)} y={Math.max(PT - 4, maxHumPt.y - 5)}
          fill="#1D9E75" fontSize="10" textAnchor="middle">▲ {Math.round(maxHumPt.val)}%</text>
      )}
      {minHumPt && (
        <text
          x={clampX(minHumPt.x)} y={Math.min(Y1 + 14, minHumPt.y + 13)}
          fill="#1D9E75" fontSize="10" textAnchor="middle">▼ {Math.round(minHumPt.val)}%</text>
      )}

      {/* Ligne de repérage au survol/tap */}
      {hoverLineEl}
    </svg>
  )
}
