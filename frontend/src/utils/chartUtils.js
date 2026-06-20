const FR_DAYS = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam']

export function niceTicks(min, max, targetCount) {
  if (min === max) return [min]
  const range = max - min
  const rawStep = range / (targetCount - 1)
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const steps = [0.5, 1, 2, 2.5, 5, 10]
  const step = (steps.find(s => s * mag >= rawStep) ?? 10) * mag
  const ticks = []
  let v = Math.ceil((min - 1e-9) / step) * step
  while (v <= max + 1e-9) {
    ticks.push(Math.round(v * 1000) / 1000)
    v += step
  }
  return ticks
}

export function linearScale(value, domainMin, domainMax, rangeMin, rangeMax) {
  if (domainMax === domainMin) return (rangeMin + rangeMax) / 2
  return rangeMin + ((value - domainMin) / (domainMax - domainMin)) * (rangeMax - rangeMin)
}

export function formatHoverLabel(date, period) {
  if (period === '12h' || period === '24h') {
    return date.toLocaleTimeString('fr', { hour: '2-digit', minute: '2-digit' })
  }
  if (period === '7d') {
    return date.toLocaleDateString('fr', { weekday: 'short', day: 'numeric', month: 'long' })
  }
  return date.toLocaleDateString('fr', { day: 'numeric', month: 'long' })
}

export function smooth(pts) {
  if (pts.length === 0) return ''
  return pts.map((p, i) => {
    if (i === 0) return `M ${p[0].toFixed(1)} ${p[1].toFixed(1)}`
    const prev = pts[i - 1]
    const cx = ((prev[0] + p[0]) / 2).toFixed(1)
    return `C ${cx} ${prev[1].toFixed(1)}, ${cx} ${p[1].toFixed(1)}, ${p[0].toFixed(1)} ${p[1].toFixed(1)}`
  }).join(' ')
}

export function getXTicks(releves, period, xStart, xEnd) {
  if (!releves.length) return []
  const times = releves.map(r => new Date(r.recu_le).getTime())
  const minTime = Math.min(...times)
  const maxTime = Math.max(...times)
  const xOf = t => maxTime === minTime
    ? (xStart + xEnd) / 2
    : linearScale(t, minTime, maxTime, xStart, xEnd)

  const ticks = []

  if (period === '12h') {
    const start = new Date(minTime)
    start.setMinutes(0, 0, 0)
    const nextH = Math.ceil(start.getHours() / 2) * 2
    start.setHours(nextH)
    for (let t = start.getTime(); t <= maxTime; t += 2 * 3600 * 1000) {
      const d = new Date(t)
      ticks.push({ time: t, x: xOf(t), label: `${d.getHours()}h` })
    }
  } else if (period === '24h') {
    const start = new Date(minTime)
    start.setMinutes(0, 0, 0)
    const nextH = Math.ceil(start.getHours() / 3) * 3
    start.setHours(nextH)
    for (let t = start.getTime(); t <= maxTime; t += 3 * 3600 * 1000) {
      const d = new Date(t)
      ticks.push({ time: t, x: xOf(t), label: `${d.getHours()}h` })
    }
  } else if (period === '7d') {
    const start = new Date(minTime)
    start.setHours(0, 0, 0, 0)
    start.setDate(start.getDate() + 1)
    for (let t = start.getTime(); t <= maxTime; t += 24 * 3600 * 1000) {
      const d = new Date(t)
      ticks.push({ time: t, x: xOf(t), label: FR_DAYS[d.getDay()] })
    }
  } else {
    const start = new Date(minTime)
    start.setHours(0, 0, 0, 0)
    start.setDate(start.getDate() + 1)
    for (let t = start.getTime(); t <= maxTime; t += 5 * 24 * 3600 * 1000) {
      const d = new Date(t)
      ticks.push({ time: t, x: xOf(t), label: `${d.getDate()}/${d.getMonth() + 1}` })
    }
  }

  return ticks
}
