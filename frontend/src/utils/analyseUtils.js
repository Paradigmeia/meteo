export const SONDE_COLORS = {
  salon: '#BA7517',
  'chambre-parents': '#7C5CBF',
  'chambre-jade': '#D85A30',
  exterieur: '#378ADD',
}

export function sondeColor(slug) {
  return SONDE_COLORS[slug] ?? '#6B6560'
}

export const METEO_COLOR = '#EF9F27'
export const DELTA_T_COLOR = '#6B6560'
export const AVG_1H_DASH = '1 3'
export const AVG_6H_DASH = '8 4'
export const HEAT_INDEX_DASH = '1 4'
export const DEW_POINT_DASH = '3 1 1 1'

export const PERIOD_HOURS = { '12h': 12, '24h': 24, '7d': 168, '30d': 720, '90d': 2160, '1an': 8760 }

export function rangeBoundsMs(quickCode, customRange) {
  if (customRange) {
    return { start: new Date(customRange.from).getTime(), end: new Date(customRange.to).getTime() }
  }
  const end = Date.now()
  return { start: end - PERIOD_HOURS[quickCode] * 3_600_000, end }
}

export const PERIOD_OPTIONS = [
  { code: '12h', label: '12h' },
  { code: '24h', label: '24h' },
  { code: '7d', label: '7j' },
  { code: '30d', label: '30j' },
  { code: '90d', label: '90j' },
  { code: '1an', label: '1 an' },
]

// Moyenne glissante en fenêtre arrière (trailing) — adaptée aux relevés non
// équidistants (events Shelly séparés temp/hum, densités variables selon la période).
export function movingAverage(releves, windowMs) {
  const pts = releves.filter(r => r.temperature != null).map(r => ({ t: new Date(r.recu_le).getTime(), v: r.temperature }))
  const result = []
  let start = 0
  let sum = 0
  for (let i = 0; i < pts.length; i++) {
    sum += pts[i].v
    while (pts[i].t - pts[start].t > windowMs) {
      sum -= pts[start].v
      start++
    }
    result.push({ recu_le: new Date(pts[i].t).toISOString(), temperature: sum / (i - start + 1) })
  }
  return result
}

export function dailyMinMaxBand(releves) {
  const days = new Map()
  for (const r of releves) {
    if (r.temperature == null) continue
    const d = new Date(r.recu_le)
    const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`
    const dayStart = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
    const entry = days.get(key) ?? { dayStart, min: r.temperature, max: r.temperature }
    entry.min = Math.min(entry.min, r.temperature)
    entry.max = Math.max(entry.max, r.temperature)
    days.set(key, entry)
  }
  return [...days.values()]
    .sort((a, b) => a.dayStart - b.dayStart)
    .map(e => ({ dayStart: e.dayStart, dayEnd: e.dayStart + 24 * 3600 * 1000, min: e.min, max: e.max }))
}

// Chaleur ressentie (régression de Rothfusz, NWS) — formule non fournie dans la spec
// (seul le point de rosée a une formule explicite), on utilise la référence standard.
export function heatIndexC(tempC, rh) {
  if (tempC == null || rh == null || tempC <= 27 || rh <= 40) return null
  const T = tempC * 9 / 5 + 32
  const hiF = -42.379 + 2.04901523 * T + 10.14333127 * rh - 0.22475541 * T * rh
    - 0.00683783 * T * T - 0.05481717 * rh * rh + 0.00122874 * T * T * rh
    + 0.00085282 * T * rh * rh - 0.00000199 * T * T * rh * rh
  return (hiF - 32) * 5 / 9
}

// Point de rosée — formule simplifiée explicitement fournie dans SPEC.md §4.6.
export function dewPointC(tempC, rh) {
  if (tempC == null || rh == null) return null
  return tempC - ((100 - rh) / 5)
}

// Écart intérieur/extérieur : pour chaque relevé extérieur, cherche le relevé
// intérieur le plus proche dans le temps. Pas de valeur (gap) si aucun relevé
// intérieur dans la tolérance (30 min par défaut, cf. test plan issue #19).
export function computeDeltaT(interiorReleves, exteriorReleves, toleranceMs = 30 * 60 * 1000) {
  const ext = exteriorReleves.filter(r => r.temperature != null).map(r => ({ t: new Date(r.recu_le).getTime(), v: r.temperature }))
  const intr = interiorReleves.filter(r => r.temperature != null).map(r => ({ t: new Date(r.recu_le).getTime(), v: r.temperature }))
  if (!ext.length || !intr.length) return []
  const result = []
  for (const e of ext) {
    let best = null, bestDist = Infinity
    for (const i of intr) {
      const d = Math.abs(i.t - e.t)
      if (d < bestDist) { bestDist = d; best = i }
    }
    if (best && bestDist <= toleranceMs) {
      result.push({ recu_le: new Date(e.t).toISOString(), delta: best.v - e.v })
    }
  }
  return result
}

export function histogramBins(values, binSize = 0.5, domain = null) {
  if (!values.length) return []
  const start = domain ? domain[0] : Math.floor(Math.min(...values) / binSize) * binSize
  const end = domain ? domain[1] : Math.ceil(Math.max(...values) / binSize) * binSize
  const bins = []
  for (let b = start; b < end; b += binSize) bins.push({ from: b, to: b + binSize, count: 0 })
  if (bins.length === 0) bins.push({ from: start, to: start + binSize, count: 0 })
  for (const v of values) {
    const idx = Math.min(bins.length - 1, Math.max(0, Math.floor((v - start) / binSize)))
    bins[idx].count++
  }
  return bins
}

const FR_DAYS = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam']
const FR_MONTHS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun', 'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc']

// Graduations de l'axe X dérivées de l'étendue temporelle réelle plutôt que d'un
// code période fixe (12h/24h/7d/30d) — nécessaire pour couvrir 90j, 1 an et les
// plages libres (date pickers) de la vue Analyse, absentes de chartUtils.getXTicks.
export function getTimeTicks(minTime, maxTime, xOf) {
  const spanH = (maxTime - minTime) / 3_600_000
  const ticks = []
  if (spanH <= 36) {
    const start = new Date(minTime)
    start.setMinutes(0, 0, 0)
    start.setHours(Math.ceil(start.getHours() / 3) * 3)
    for (let t = start.getTime(); t <= maxTime; t += 3 * 3_600_000) {
      ticks.push({ time: t, x: xOf(t), label: `${new Date(t).getHours()}h` })
    }
  } else if (spanH <= 24 * 9) {
    const start = new Date(minTime)
    start.setHours(0, 0, 0, 0)
    start.setDate(start.getDate() + 1)
    for (let t = start.getTime(); t <= maxTime; t += 24 * 3_600_000) {
      ticks.push({ time: t, x: xOf(t), label: FR_DAYS[new Date(t).getDay()] })
    }
  } else if (spanH <= 24 * 40) {
    const start = new Date(minTime)
    start.setHours(0, 0, 0, 0)
    start.setDate(start.getDate() + 1)
    for (let t = start.getTime(); t <= maxTime; t += 5 * 24 * 3_600_000) {
      const d = new Date(t)
      ticks.push({ time: t, x: xOf(t), label: `${d.getDate()}/${d.getMonth() + 1}` })
    }
  } else if (spanH <= 24 * 100) {
    const start = new Date(minTime)
    start.setHours(0, 0, 0, 0)
    start.setDate(start.getDate() + 1)
    for (let t = start.getTime(); t <= maxTime; t += 10 * 24 * 3_600_000) {
      const d = new Date(t)
      ticks.push({ time: t, x: xOf(t), label: `${d.getDate()}/${d.getMonth() + 1}` })
    }
  } else {
    const start = new Date(minTime)
    start.setHours(0, 0, 0, 0)
    start.setDate(1)
    start.setMonth(start.getMonth() + 1)
    for (let t = start.getTime(); t <= maxTime;) {
      ticks.push({ time: t, x: xOf(t), label: FR_MONTHS[new Date(t).getMonth()] })
      const d = new Date(t)
      d.setMonth(d.getMonth() + 1)
      t = d.getTime()
    }
  }
  return ticks
}

const PREFS_KEY = 'analyse-prefs-v1'

export function loadAnalysePrefs() {
  try {
    const raw = window.localStorage.getItem(PREFS_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveAnalysePrefs(prefs) {
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs))
  } catch {}
}
