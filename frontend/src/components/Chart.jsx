export default function Chart({ releves }) {
  if (!releves || releves.length < 2) {
    return (
      <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#B5B0A8', fontSize: 13 }}>
        Pas assez de données
      </div>
    )
  }

  const W = 340, H = 140, PAD = 12

  const temps = releves.map(r => r.temperature)
  const humReleves = releves.filter(r => r.humidite != null)

  const minT = Math.min(...temps), maxT = Math.max(...temps)

  const xOf = i => PAD + (i / (releves.length - 1)) * (W - 2 * PAD)
  const yOfT = v => H - PAD - ((v - minT) / (maxT - minT || 1)) * (H - 2 * PAD)

  function smooth(pts) {
    return pts.map((p, i) => {
      if (i === 0) return `M ${p[0]} ${p[1]}`
      const prev = pts[i - 1]
      const cx = (prev[0] + p[0]) / 2
      return `C ${cx} ${prev[1]}, ${cx} ${p[1]}, ${p[0]} ${p[1]}`
    }).join(' ')
  }

  const tempPts = releves.map((_, i) => [xOf(i), yOfT(temps[i])])

  let humPath = null
  if (humReleves.length >= 2) {
    const hums = humReleves.map(r => r.humidite)
    const minH = Math.min(...hums), maxH = Math.max(...hums)
    const yOfH = v => H - PAD - ((v - minH) / (maxH - minH || 1)) * (H - 2 * PAD)
    const humIdxMap = humReleves.map(r => releves.indexOf(r))
    const humPts = humIdxMap.map((ri, i) => [xOf(ri), yOfH(hums[i])])
    humPath = smooth(humPts)
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H }}>
      <path d={smooth(tempPts)} fill="none" stroke="#BA7517" strokeWidth="2" strokeLinejoin="round" />
      {humPath && <path d={humPath} fill="none" stroke="#1D9E75" strokeWidth="2" strokeLinejoin="round" strokeDasharray="4 2" />}
    </svg>
  )
}
