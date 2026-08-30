export const SONDE_COLORS = {
  salon: '#BA7517',
  'chambre-parents': '#7C5CBF',
  'chambre-jade': '#D85A30',
  exterieur: '#378ADD',
}

export function sondeColor(slug) {
  return SONDE_COLORS[slug] ?? '#6B6560'
}

// Couleurs d'axe : température (ambre) et humidité (teal), partagées entre les
// graduations du graphique et les puces du filtre "Type de mesure".
export const TEMP_AXIS_COLOR = '#BA7517'
export const HUM_AXIS_COLOR = '#1D9E75'

export const METEO_COLOR = '#EF9F27'
export const AVG_1H_DASH = '1 3'
export const AVG_6H_DASH = '8 4'

export const PERIOD_HOURS = { '12h': 12, '24h': 24, '7d': 168, '30d': 720, '90d': 2160, '1an': 8760 }

// Plafond de la plage libre, en heures. Doit rester aligné sur MAX_RANGE_HOURS
// de backend/main.py : le serveur refuse au-delà par un 400 (issue #37), et une
// divergence se traduirait par un bandeau d'échec là où l'interface devrait
// expliquer ce qui ne va pas. C'est la plus longue période prédéfinie.
export const MAX_RANGE_HOURS = 8760

// La borne est volontairement inclusive : une plage d'exactement un an passe,
// des deux côtés — le serveur rejette sur `>`, pas sur `>=`.
export function isRangeTooLong(customRange) {
  if (!customRange?.from || !customRange?.to) return false
  const heures = (new Date(customRange.to) - new Date(customRange.from)) / 3_600_000
  // Une date illisible donne NaN, et `NaN > x` vaut false : la requête part, et
  // c'est voulu — le 400 « format de date invalide » du serveur est plus précis
  // que « plage trop large »
  return heures > MAX_RANGE_HOURS
}

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
