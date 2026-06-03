export default function Chart({ releves }) {
  if (!releves || releves.length < 2) {
    return (
      <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#B5B0A8', fontSize: 13 }}>
        Pas assez de données
      </div>
    )
  }

  const W = 340, H = 140, PAD = 12

  const tempReleves = releves.filter(r => r.temperature != null)
  const humReleves  = releves.filter(r => r.humidite != null)

  const times = releves.map(r => new Date(r.recu_le).getTime())
  const minTime = Math.min(...times), maxTime = Math.max(...times)
  const xOfTime = t => PAD + ((t - minTime) / (maxTime - minTime || 1)) * (W - 2 * PAD)

  function smooth(pts) {
    return pts.map((p, i) => {
      if (i === 0) return `M ${p[0]} ${p[1]}`
      const prev = pts[i - 1]
      const cx = (prev[0] + p[0]) / 2
      return `C ${cx} ${prev[1]}, ${cx} ${p[1]}, ${p[0]} ${p[1]}`
    }).join(' ')
  }

  let tempPath = null
  if (tempReleves.length >= 2) {
    const temps = tempReleves.map(r => r.temperature)
    const minT = Math.min(...temps), maxT = Math.max(...temps)
    const yOfT = v => H - PAD - ((v - minT) / (maxT - minT || 1)) * (H - 2 * PAD)
    const tempPts = tempReleves.map(r => [xOfTime(new Date(r.recu_le).getTime()), yOfT(r.temperature)])
    tempPath = smooth(tempPts)
  }

  let humPath = null
  if (humReleves.length >= 2) {
    const hums = humReleves.map(r => r.humidite)
    const minH = Math.min(...hums), maxH = Math.max(...hums)
    const yOfH = v => H - PAD - ((v - minH) / (maxH - minH || 1)) * (H - 2 * PAD)
    const humPts = humReleves.map(r => [xOfTime(new Date(r.recu_le).getTime()), yOfH(r.humidite)])
    humPath = smooth(humPts)
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: H }}>
      {tempPath && <path d={tempPath} fill="none" stroke="#BA7517" strokeWidth="2" strokeLinejoin="round" />}
      {humPath && <path d={humPath} fill="none" stroke="#1D9E75" strokeWidth="2" strokeLinejoin="round" strokeDasharray="4 2" />}
    </svg>
  )
}
