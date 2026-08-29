// Noms d'icônes Tabler, résolus par le composant Icon (cf. components/Icon.jsx).
// 'haze' et 'droplets' remplacent 'cloud-sun' et 'cloud-drizzle', qui n'existent
// pas dans Tabler 3.19.0 : ces deux conditions n'affichaient donc aucune icône
// tant que la police était chargée depuis le CDN (issue #50)
export const WMO_ICONS = {
  0: 'sun',
  1: 'sun',
  2: 'haze',
  3: 'cloud',
  45: 'cloud-fog',
  48: 'cloud-fog',
  51: 'droplets',
  53: 'droplets',
  55: 'droplets',
  61: 'cloud-rain',
  63: 'cloud-rain',
  65: 'cloud-rain',
  71: 'snowflake',
  73: 'snowflake',
  75: 'snowflake',
  80: 'cloud-rain',
  81: 'cloud-rain',
  82: 'cloud-rain',
  95: 'cloud-storm',
  96: 'cloud-storm',
  99: 'cloud-storm',
}

export const WMO_LABELS = {
  0: 'Ciel dégagé',
  1: 'Peu nuageux',
  2: 'Partiellement nuageux',
  3: 'Couvert',
  45: 'Brouillard',
  48: 'Brouillard givrant',
  51: 'Bruine légère',
  53: 'Bruine',
  55: 'Bruine dense',
  61: 'Pluie légère',
  63: 'Pluie',
  65: 'Pluie forte',
  71: 'Neige légère',
  73: 'Neige',
  75: 'Neige forte',
  80: 'Averses légères',
  81: 'Averses',
  82: 'Averses fortes',
  95: 'Orage',
  96: 'Orage avec grêle',
  99: 'Orage violent',
}

export function wmoIcon(code) {
  return WMO_ICONS[code] ?? 'cloud'
}

export function wmoLabel(code) {
  return WMO_LABELS[code] ?? 'Inconnu'
}

export function windDir(deg) {
  const dirs = ['N','NE','E','SE','S','SO','O','NO']
  return dirs[Math.round(deg / 45) % 8]
}

export function formatAgo(isoStr) {
  if (!isoStr) return null
  const diff = (Date.now() - new Date(isoStr).getTime()) / 1000
  if (diff < 60) return 'à l\'instant'
  if (diff < 3600) return `il y a ${Math.floor(diff / 60)} min`
  if (diff < 86400) return `il y a ${Math.floor(diff / 3600)} h`
  return `il y a ${Math.floor(diff / 86400)} j`
}

export function isOffline(isoStr) {
  if (!isoStr) return true
  return (Date.now() - new Date(isoStr).getTime()) > 3 * 3600 * 1000
}
