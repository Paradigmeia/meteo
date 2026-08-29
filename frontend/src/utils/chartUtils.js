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

// --- Géométrie curseur → viewBox -------------------------------------------
// Convertit l'abscisse client d'un pointeur en abscisse dans le repère du
// viewBox d'un <svg>. Partagé par AnalyseChart et HistoriqueChart : avant
// l'issue #30 chacun avait sa version, dont une fausse dès qu'il y a
// letterboxing (issue #26).

// Conversion exacte par la matrice écran→viewBox du <svg>. Elle intègre toute
// transformation appliquée au dessin — mise à l'échelle du preserveAspectRatio,
// recentrage, transformations CSS d'un ancêtre. La projection est écrite à la
// main (x' = a·x + c·y + e, la ligne d'un produit matriciel 2D) plutôt que
// déléguée à DOMPoint : la fonction reste ainsi de l'arithmétique testable hors
// navigateur. Renvoie null si la matrice est indisponible (svg non rendu) ou
// non inversible — inverse() rend alors une matrice de NaN.
export function viewBoxXFromClient(clientX, clientY, ctm) {
  const inverse = ctm?.inverse?.()
  if (!inverse) return null
  const x = inverse.a * clientX + inverse.c * clientY + inverse.e
  return Number.isFinite(x) ? x : null
}

// Équivalent arithmétique du calcul ci-dessus pour le preserveAspectRatio par
// défaut ("xMidYMid meet") : le contenu est mis à l'échelle du plus petit des
// deux rapports, puis centré dans la boîte. Sert de repli quand la matrice est
// indisponible, et rend la géométrie testable sans DOM. Renvoie null si la
// boîte est dégénérée (svg non affiché, environnement sans layout).
export function viewBoxXFromRect(clientX, rect, viewBoxWidth, viewBoxHeight) {
  if (!rect) return null
  const scale = Math.min(rect.width / viewBoxWidth, rect.height / viewBoxHeight)
  const x = (clientX - rect.left - (rect.width - viewBoxWidth * scale) / 2) / scale
  // Une échelle nulle — boîte de taille zéro (svg non affiché, environnement
  // sans layout) ou viewBox dégénéré — rend x non fini : pas d'abscisse à tirer.
  return Number.isFinite(x) ? x : null
}

// Composition des deux pour un évènement souris ou tactile React sur un <svg>.
// Les dimensions du viewBox sont lues sur l'élément lui-même plutôt que passées
// par l'appelant : elles ne peuvent pas diverger de celles réellement rendues
// (AnalyseChart en mode Séparé attache les mêmes gestionnaires à deux panneaux
// de hauteurs différentes). Renvoie null si la position n'est pas calculable —
// mieux vaut ne pas déplacer le curseur que le poser au mauvais endroit.
export function viewBoxXFromPointerEvent(event) {
  const source = event.touches ? event.touches[0] : event
  if (!source) return null
  const svg = event.currentTarget
  const fromCtm = viewBoxXFromClient(source.clientX, source.clientY, svg.getScreenCTM?.())
  if (fromCtm !== null) return fromCtm

  const viewBox = svg.viewBox?.baseVal
  if (!viewBox) return null
  const x = viewBoxXFromRect(source.clientX, svg.getBoundingClientRect(), viewBox.width, viewBox.height)
  return x === null ? null : x + viewBox.x
}
